"""Synthetic fold for the plugin tests: random graph_tokens.pt + build_sft-format graph/text SFT files.

Prompts follow build_sft.build_prompt (step lines "[sid] agent | phase | round r <graph>" + excerpt, interaction lines
"<graph> instr"); excerpt lengths vary so that some prompts exceed max_len=512 tokens and lose their head (and the
graph placeholders in it) to truncation.
Usage: python make_synthetic.py <out_dir> [n_train=20] [seed=0]
"""
import json
import os
import random
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..', '..')))
from hgfm.llm.build_sft import SYSTEM  # noqa: E402

WORDS = ('patient fever cough dyspnea antibiotic dosage renal hepatic consult cardiology imaging biopsy diagnosis '
         'differential triage specialist recommends contradicts guideline evidence round final answer').split()


def prompt(rng, n_steps, n_edges, use_graph):
    lines, refs = [], []
    K = min(n_steps, 10)
    for i in range(K):
        n_words = rng.choice([2, 5, 10, 40])
        line = f'[s{i}] agent{i % 3} | phase{i % 2} | round {i // 3}' + (' <graph>' if use_graph else '')
        line += '\n    excerpt: ' + ' '.join(rng.choice(WORDS) for _ in range(n_words))
        lines.append(line)
        if use_graph: refs.append(['node', i])
    elines = []
    for k in range(min(n_edges, 4)):
        elines.append(('<graph> ' if use_graph else '') + f'agent{k} asks agent{k + 1} to review step s{k}')
        if use_graph: refs.append(['edge', k])
    user = ('Question:\n' + ' '.join(rng.choice(WORDS) for _ in range(rng.choice([10, 40, 120]))) +
            '\n\nSystem\'s final answer: B\n\nTrajectory (most relevant steps):\n' + '\n'.join(lines) +
            ('\n\nInteraction events around the target:\n' + '\n'.join(elines) if elines else '') +
            '\n\nFailure mode 1.1: Fake\nDefinition: d\nGuideline: g\n\nTarget: step [s0] by agent0 (phase0). '
            'Is this failure mode present? Answer yes or no.')
    return user, refs


def main(out, n_train=20, seed=0):
    rng = random.Random(seed); torch.manual_seed(seed)
    os.makedirs(out, exist_ok=True)
    tokens, rows = {}, []
    for r in range(n_train + 6):
        run = f'run{r:03d}'; n_steps = rng.randint(6, 14); n_edges = rng.randint(2, 6)
        tokens[run] = {'h': torch.randn(n_steps, 192), 'm': torch.randn(n_edges, 192), 'split': 'train' if r < n_train else 'test',
                       'step_prob': torch.rand(n_steps, 5)}
        rows.append((run, n_steps, n_edges, rng.getstate()))
    torch.save(tokens, os.path.join(out, 'graph_tokens.pt'))
    for variant, use_graph in (('sft_graph', True), ('sft_text', False)):
        os.makedirs(os.path.join(out, variant), exist_ok=True)
        with open(os.path.join(out, variant, 'train.jsonl'), 'w') as ft, open(os.path.join(out, variant, 'eval_human.jsonl'), 'w') as fe:
            for j, (run, n_steps, n_edges, state) in enumerate(rows):
                prng = random.Random(); prng.setstate(state)   # identical text for both variants
                user, refs = prompt(prng, n_steps, n_edges, use_graph)
                if j < n_train:
                    ft.write(json.dumps({'run_id': run, 'system': SYSTEM, 'user': user, 'graph_refs': refs,
                                         'answer': 'yes' if j % 2 == 0 else 'no', 'code': '1.1'}) + '\n')
                else:
                    fe.write(json.dumps({'run_id': run, 'i': 0, 'code': '1.1', 'label': j % 2, 'auditor': 1 - j % 2,
                                         'inst': f'{run}|1.1', 'system': SYSTEM, 'user': user, 'graph_refs': refs}) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1], *(int(x) for x in sys.argv[2:]))
