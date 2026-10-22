"""Equivalence of the MS-Swift path (plugin.py) with GraphTokenLM / train.py / eval.py (CPU, fp32, tiny model).

  (a) same weights + same batch -> same loss (graph and text variant) and same gradients
  (b) <graph> input embeddings == projector output; all other embeddings == token embeddings
  (c) truncation keeps the end of the prompt and drops the oldest graph vectors exactly like train.batches
      (also checked with the Qwen3-8B tokenizer, where enable_thinking=False matters, if it is cached)
  (e) with --ckpt: logit(yes)-logit(no) from a swift checkpoint == GraphTokenLM(ckpt=...) as used by eval.py
Usage: python test_equivalence.py --lm <Qwen2.5-0.5B-Instruct dir> --syn <make_synthetic dir> [--qwen3 <Qwen3-8B dir>]
          [--ckpt <swift checkpoint dir> --variant graph|text]
"""
import argparse
import gc
import json
import os
import sys
import tempfile

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, V2)
os.environ.setdefault('USE_HF', '1')
from swift.utils import import_external_file  # noqa: E402

plugin = import_external_file(os.path.join(HERE, '..', 'plugin.py'))
convert = import_external_file(os.path.join(HERE, '..', 'prepare_data.py')).convert
from hgfm.llm.model import GraphTokenLM, graph_vectors  # noqa: E402
from hgfm.llm.train import batches, encode  # noqa: E402

MAXLEN = 512
RES = {}


def jl(p):
    return [json.loads(l) for l in open(p)]


def swift_parts(lm, data_file, out_dir):
    """Model/template/trainer built by the same pipeline objects `swift sft` uses."""
    from swift.pipelines.train.sft import SwiftSft
    from swift.trainers import TrainerFactory
    argv = ['--model', lm, '--model_type', plugin.MODEL_TYPE, '--template', plugin.TEMPLATE_TYPE, '--tuner_type', plugin.TUNER_TYPE,
            '--lora_rank', '8', '--lora_alpha', '32', '--lora_dropout', '0.1', '--target_modules', 'q_proj', 'k_proj', 'v_proj',
            '--optimizer', plugin.OPTIMIZER, '--learning_rate', '1e-4', '--aligner_lr', '1e-3', '--weight_decay', '0',
            '--max_length', str(MAXLEN), '--torch_dtype', 'float32', '--dataset', data_file, '--split_dataset_ratio', '0',
            '--strict', 'true', '--per_device_train_batch_size', '4', '--output_dir', out_dir, '--report_to', 'none',
            '--gradient_checkpointing', 'false', '--dataset_shuffle', 'false']
    sft = SwiftSft(argv)
    train_ds, _ = sft._prepare_dataset()
    model = sft.prepare_model(sft.args, sft.model, template=sft.template, train_dataset=train_ds)
    trainer = TrainerFactory.get_trainer_cls(sft.args)(model=model, args=sft.args.training_args, template=sft.template,
                                                         train_dataset=train_ds, eval_dataset=None)
    return sft, model, trainer, train_ds


def train_mode_no_dropout(hf):
    """train() so that gradient checkpointing is active (CPU RAM), dropout p=0 so both sides are deterministic."""
    hf.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False}); hf.enable_input_require_grads()
    for mod in hf.modules():
        if isinstance(mod, torch.nn.Dropout): mod.p = 0.0


def original_side(lm, rows, tokens, use_graph, dump):
    torch.manual_seed(0)
    m = GraphTokenLM(lm, dtype=torch.float32, use_graph=use_graph)
    for n, p in m.lm.named_parameters():   # make LoRA non-trivial (B is zero at init)
        if 'lora_B' in n: p.data.normal_(0, 0.01)
    m.train(); train_mode_no_dropout(m.lm.get_base_model())
    ids, att, gv, lab = next(batches(m, rows, tokens, 4, MAXLEN, 'cpu'))
    loss = m(ids, att, gv, lab); loss.backward()
    grads = {n: p.grad.clone() for n, p in m.lm.named_parameters() if p.grad is not None}
    grads.update({f'proj.{n}': p.grad.clone() for n, p in m.proj.named_parameters() if p.grad is not None})
    with torch.no_grad():
        emb = m.embed(ids, gv)
        g_out = m.proj(gv) if (use_graph and gv is not None and gv.numel()) else None
    sd = {k: v for k, v in m.lm.state_dict().items() if 'lora_' in k or 'embed_tokens' in k or 'lm_head' in k}
    torch.save({'loss': loss.item(), 'ids': ids, 'att': att, 'lab': lab, 'gv': gv, 'emb': emb, 'g_out': g_out,
                'grads': grads, 'lm_sd': sd, 'proj_sd': m.proj.state_dict(), 'graph_id': m.graph_id}, dump)
    del m; gc.collect()


def test_ab(lm, syn, variant):
    use_graph = variant == 'graph'
    raw = jl(f'{syn}/sft_{variant}/train.jsonl')[:4]
    tokens = torch.load(f'{syn}/graph_tokens.pt')
    dump = os.path.join(tempfile.mkdtemp(), 'orig.pt')
    original_side(lm, raw, tokens, use_graph, dump)
    O = torch.load(dump, weights_only=False)

    sft, model, trainer, train_ds = swift_parts(lm, f'{syn}/sft_{variant}/swift_train.jsonl', tempfile.mkdtemp())
    template = sft.template
    missing, unexpected = model.load_state_dict(O['lm_sd'], strict=False)
    assert not unexpected, unexpected
    inner = model.get_base_model()
    getattr(inner, plugin.PROJ_NAME).load_state_dict(O['proj_sd'])
    assert inner.graph_token_id == O['graph_id']
    model.train(); train_mode_no_dropout(inner)
    # rows through swift's dataset loader (dataset_shuffle false -> file order); extra columns must survive
    assert [train_ds.dataset[i]['run_id'] for i in range(4)] == [r['run_id'] for r in raw]
    enc = [train_ds[i] for i in range(4)]
    batch = template.data_collator(enc)
    assert torch.equal(batch['input_ids'], O['ids']) and torch.equal(batch['labels'], O['lab'])
    assert torch.equal(batch['attention_mask'], O['att'])
    captured = {}
    inner.model.register_forward_pre_hook(lambda mod, a, kw: captured.update(emb=kw.get('inputs_embeds')), with_kwargs=True)
    template.register_post_encode_hook([model])
    inputs = trainer._prepare_inputs(batch)
    loss = trainer.compute_loss(model, inputs)
    loss.backward()
    template.remove_post_encode_hook()
    d_loss = abs(loss.item() - O['loss'])
    gmax = grel = gref = 0.0; cos_min = 1.0; worst = None
    for n, p in model.named_parameters():
        if p.grad is None: continue
        key = f"proj.{n.split(plugin.PROJ_NAME + '.', 1)[1]}" if plugin.PROJ_NAME in n else n
        g0 = O['grads'][key]; d = (p.grad - g0).abs().max().item()
        r = d / max(g0.abs().max().item(), 1e-12)
        if r > grel: grel, worst = r, key
        gmax = max(gmax, d); gref = max(gref, g0.abs().max().item())
        cos_min = min(cos_min, torch.nn.functional.cosine_similarity(p.grad.flatten(), g0.flatten(), dim=0).item())
    n_grads = sum(p.grad is not None for p in model.parameters())
    assert n_grads == len(O['grads']), (n_grads, len(O['grads']))
    res = {'loss_orig': O['loss'], 'loss_swift': loss.item(), 'abs_diff': d_loss, 'max_grad_abs_diff': gmax, 'max_abs_grad': gref, 'global_grad_rel_diff': gmax / gref,
           'worst_tensor_rel_diff': grel, 'worst_tensor': worst, 'min_grad_cosine': cos_min,
           'n_grad_tensors': n_grads, 'logits_to_keep': str(type(inputs.get('logits_to_keep')).__name__)}
    # (b) placeholder replacement
    emb = captured['emb']
    if use_graph:
        mask = batch['input_ids'] == O['graph_id']
        with torch.no_grad():
            tok_emb = inner.get_input_embeddings()(batch['input_ids'])
            proj_out = getattr(inner, plugin.PROJ_NAME)(O['gv'])
        res['b_n_placeholders'] = int(mask.sum())
        res['b_placeholder_vs_proj'] = (emb[mask] - proj_out).abs().max().item()
        res['b_placeholder_vs_orig_proj'] = (emb[mask] - O['g_out']).abs().max().item()
        res['b_other_vs_token_emb'] = (emb[~mask] - tok_emb[~mask]).abs().max().item()
        res['b_full_vs_GraphTokenLM_embed'] = (emb - O['emb']).abs().max().item()
        assert res['b_placeholder_vs_proj'] == 0 and res['b_other_vs_token_emb'] == 0
    else:
        res['b_inputs_embeds_passed'] = emb is not None   # text variant: no graph tensors -> plain input_ids path
        assert 'graph_vecs' not in batch
    assert d_loss < 1e-4 and gmax / gref < 1e-4 and cos_min > 0.99999, res
    RES[f'a_b_{variant}'] = res
    del model, trainer, sft; gc.collect()


class _Tok:   # minimal stand-in for GraphTokenLM in train.encode (needs .tok and .graph_id)
    def __init__(self, path):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(path)
        if self.tok.pad_token is None: self.tok.pad_token = self.tok.eos_token
        self.tok.add_special_tokens({'additional_special_tokens': [plugin.GRAPH_TOKEN]})
        self.graph_id = self.tok.convert_tokens_to_ids(plugin.GRAPH_TOKEN)


def test_c(lm, syn, tag, MAXLEN=MAXLEN):
    from swift.model import get_model_processor
    from swift.template import get_template
    _, proc = get_model_processor(lm, model_type=plugin.MODEL_TYPE, load_model=False)
    template = get_template(proc, template_type=plugin.TEMPLATE_TYPE, max_length=MAXLEN, truncation_strategy='left')
    template.set_mode('train')
    ref = _Tok(lm)
    assert ref.graph_id == proc.convert_tokens_to_ids(plugin.GRAPH_TOKEN)
    tokens = torch.load(f'{syn}/graph_tokens.pt')
    out = {}
    for variant in ('graph', 'text'):
        n = n_trunc = n_drop = n_ph_total = 0
        for s in jl(f'{syn}/sft_{variant}/train.jsonl'):
            p, a = encode(ref, s, MAXLEN)
            full_p, _ = encode(ref, s, 10 ** 9)
            g = graph_vectors(s, tokens); n_ph = sum(t == ref.graph_id for t in p)
            g = g[-n_ph:] if n_ph else g[:0]   # train.batches
            e = template.encode(convert(s))
            assert e['input_ids'] == p + a and e['labels'] == [-100] * len(p) + a, s['run_id']
            ge = e.get('graph_vecs', torch.zeros(0, g.shape[1]))
            assert torch.equal(ge, g), s['run_id']
            assert len(e['input_ids']) <= MAXLEN
            n += 1; n_trunc += len(full_p) != len(p); n_drop += len(s['graph_refs']) - n_ph; n_ph_total += n_ph
            if len(full_p) != len(p):
                assert p == full_p[-len(p):]   # the END is kept
        out[variant] = {'rows': n, 'truncated_rows': n_trunc, 'graph_vectors_dropped': n_drop, 'graph_vectors_kept': n_ph_total}
    # collator: padded graph tensor + counts reproduce the concatenation used by GraphTokenLM
    rows = jl(f'{syn}/sft_graph/train.jsonl')[:4]
    b = template.data_collator([template.encode(convert(s)) for s in rows])
    cat = torch.cat([b['graph_vecs'][i, :c] for i, c in enumerate(b['graph_counts'].tolist())])
    o = next(batches(type('M', (), {'tok': ref.tok, 'graph_id': ref.graph_id})(), rows, tokens, 4, MAXLEN, 'cpu'))
    assert torch.equal(cat, o[2]) and torch.equal(b['input_ids'], o[0])
    out['collator_counts'] = b['graph_counts'].tolist()
    RES[f'c_{tag}'] = out


def test_e(lm, syn, ckpt, variant):
    ev = import_external_file(os.path.join(HERE, '..', 'eval_swift.py'))
    rows = jl(f'{syn}/sft_{variant}/eval_human.jsonl')
    model, template = ev.load(lm, ckpt, torch.float32, MAXLEN, 'cpu')
    tok = template.tokenizer
    yes, no = tok('yes', add_special_tokens=False)['input_ids'][0], tok('no', add_special_tokens=False)['input_ids'][0]
    s_sw = [ev.score(model, template, r, yes, no) for r in rows]
    del model; gc.collect()
    # GraphTokenLM(ckpt=...) expects <ckpt>/lora (adapter + tokenizer) and <ckpt>/projector.pt
    d = tempfile.mkdtemp(); os.makedirs(f'{d}/lora')
    for f in ('adapter_config.json', 'adapter_model.safetensors'):
        os.symlink(os.path.join(ckpt, f), f'{d}/lora/{f}')
    os.symlink(os.path.join(ckpt, 'projector.pt'), f'{d}/projector.pt')
    _Tok(lm).tok.save_pretrained(f'{d}/lora')
    m = GraphTokenLM(lm, dtype=torch.float32, use_graph=variant == 'graph', ckpt=d).eval()
    tokens = torch.load(f'{syn}/graph_tokens.pt')
    s_o = []
    with torch.no_grad():
        for s in rows:   # eval.py main loop
            p, _ = encode(m, {**s, 'answer': ''}, MAXLEN, with_answer=False)
            g = graph_vectors(s, tokens); n_ph = sum(1 for t in p if t == m.graph_id); g = g[-n_ph:] if n_ph else g[:0]
            ids = torch.tensor([p]); logits = m(ids, torch.ones_like(ids), g)[0]
            s_o.append(float(logits[yes] - logits[no]))
    diff = max(abs(a - b) for a, b in zip(s_sw, s_o))
    RES[f'e_{variant}'] = {'n': len(rows), 'scores_swift': [round(x, 5) for x in s_sw], 'scores_GraphTokenLM': [round(x, 5) for x in s_o],
                           'max_abs_diff': diff}
    assert diff < 1e-4


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lm'); ap.add_argument('--syn'); ap.add_argument('--qwen3', default='')
    ap.add_argument('--ckpt', default=''); ap.add_argument('--variant', default='graph'); ap.add_argument('--only', default='abc')
    a = ap.parse_args()
    os.environ['MHT_GRAPH_TOKENS'] = f'{a.syn}/graph_tokens.pt'
    if 'c' in a.only:
        test_c(a.lm, a.syn, 'qwen2.5')
        test_c(a.lm, a.syn, 'qwen2.5_maxlen300', MAXLEN=300)   # harsher truncation: more placeholders cut
        if a.qwen3: test_c(a.qwen3, a.syn, 'qwen3_tokenizer')
    if 'a' in a.only:
        test_ab(a.lm, a.syn, 'graph'); test_ab(a.lm, a.syn, 'text')
    if a.ckpt:
        test_e(a.lm, a.syn, a.ckpt, a.variant)
    print('RESULTS ' + json.dumps(RES, indent=1))
