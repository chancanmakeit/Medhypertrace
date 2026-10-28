"""E1 (round 67): patch a checkout of deeplearning-wisc/OAT for the pre-registered proxy-swap experiment.

  python oat_patch.py <OAT_dir>

1. dataset "traceelephant_gc" (dataset/traceelephant_gc/Algorithm-Generated/*.json, written by te_to_ww.py), loaded with
   OAT's own Who&When loader, so serialisation and model-step flags follow OAT's rules exactly.
2. extraction (only when env OAT_LAST_LAYER_ONLY=1): one forward of the base transformer -> last_hidden_state (after the
   final norm, = hidden_states[-1] of the original code), stored as [T, 1, H]; the original stores all layers, which
   for a 76k-token run does not fit in 48 GB. DEFAULT_LAYER = -1 selects the same layer either way.
3. length routing for the pre-registered YaRN rule: OAT_LEN=le32k skips sequences > 32,768 tokens (native pass);
   OAT_LEN=gt32k extracts only those, with the model loaded with YaRN x4 (OAT_YARN=4). No truncation in either pass.
4. `ood` also writes predictions_seed<k>.json for every seed.\nNothing else (PCA, CDE, gate, seeds, CORAL, metrics) is touched. Idempotent: refuses to patch twice.
"""
import os, sys


def sub(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:60])
    open(path, "w").write(s.replace(old, new))


def main(d):
    cfg, dp, ex = (os.path.join(d, f) for f in ("config.py", "data_pipeline.py", "extract_states.py"))
    if "traceelephant_gc" in open(cfg).read():
        print("already patched"); return
    sub(cfg, 'DATASETS = ("mcp_atlas", "who_and_when")', 'DATASETS = ("mcp_atlas", "who_and_when", "traceelephant_gc")')
    sub(cfg, '    if dataset == "who_and_when":\n        return WHO_AND_WHEN_DATA_DIR\n',
        '    if dataset == "who_and_when":\n        return WHO_AND_WHEN_DATA_DIR\n'
        '    if dataset == "traceelephant_gc":\n        return DATASET_DIR / "traceelephant_gc"\n')
    sub(cfg, 'MAX_SEQ_LENGTH = 262144', 'MAX_SEQ_LENGTH = 262144\nimport os as _os\nif _os.environ.get("OAT_MODEL_NAME"): MODEL_NAME = _os.environ["OAT_MODEL_NAME"]')
    sub(dp, '    if dataset == "who_and_when":\n        return load_who_and_when_trajectories()\n',
        '    if dataset == "who_and_when":\n        return load_who_and_when_trajectories()\n'
        '    if dataset == "traceelephant_gc":\n'
        '        T = load_who_and_when_trajectories(data_dir=config.DATASET_DIR / "traceelephant_gc")\n'
        '        for t in T: t["dataset_source"] = "traceelephant_gc"\n'
        '        return T\n')
    sub(ex, '    input_device = _get_model_input_device(model)\n    outputs = model(',
        '    input_device = _get_model_input_device(model)\n'
        '    import os as _os\n'
        '    _len = _os.environ.get("OAT_LEN", "")\n'
        '    if (_len == "le32k" and seq_len > 32768) or (_len == "gt32k" and seq_len <= 32768):\n'
        '        return "SKIP_LEN"\n'
        '    if _os.environ.get("OAT_LAST_LAYER_ONLY") == "1":\n'
        '        base = model.get_base_model() if hasattr(model, "get_base_model") else model.model\n'
        '        hs = base(input_ids=input_ids.to(input_device), attention_mask=encoding["attention_mask"].to(input_device),\n'
        '                  use_cache=False, return_dict=True).last_hidden_state[0].float()\n'
        '        T = len(char_boundaries)\n'
        '        result = torch.zeros(T, 1, hs.shape[-1], dtype=torch.float32)\n'
        '        for step_idx, loc in enumerate(step_locations):\n'
        '            if aggregation == "last":\n'
        '                result[step_idx, 0] = hs[loc].cpu()\n'
        '            elif loc[0] <= loc[1]:\n'
        '                result[step_idx, 0] = hs[loc[0]: loc[1] + 1].mean(dim=0).cpu()\n'
        '            else:\n'
        '                result[step_idx, 0] = hs[loc[1]].cpu()\n'
        '        return result\n'
        '    outputs = model(')
    sub(ex, '        if hidden is None:\n            skipped += 1\n            continue\n',
        '        if isinstance(hidden, str):\n            continue\n'
        '        if hidden is None:\n            skipped += 1\n            continue\n')
    sub(ex, '    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)',
        '    import os as _os\n'
        '    if _os.environ.get("OAT_YARN"):\n'
        '        f = float(_os.environ["OAT_YARN"])\n'
        '        model_kwargs["rope_scaling"] = {"rope_type": "yarn", "factor": f, "original_max_position_embeddings": 32768}\n'
        '        model_kwargs["max_position_embeddings"] = int(32768 * f)\n'
        '    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)')
    rp = os.path.join(d, "run_pipeline.py")
    # every seed's predictions of `ood` (the original keeps only the last seed's), for the pre-registered paired analysis
    sub(rp, '''        metrics, preds = _train_eval_once(source_success, target_failure, seed, args)
        seed_metrics.append(metrics)
''', '''        metrics, preds = _train_eval_once(source_success, target_failure, seed, args)
        seed_metrics.append(metrics)
        _od = config.RESULTS_DIR / "ood" / f"{args.train_dataset}_to_{args.test_dataset}" / "OAT_coral"; _od.mkdir(parents=True, exist_ok=True)
        with open(_od / f"predictions_seed{run_idx}.json", "w") as _f:
            json.dump([_jsonable_prediction(p) for p in preds], _f)
''')
    print("patched", d)


if __name__ == "__main__":
    main(sys.argv[1])
