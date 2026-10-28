"""Confound check for the post-hoc E2 lead NLL_base - NLL_tapt (round 68; diagnostic, on the same E3 data, not a test).

  python e1e3_confounds.py [--root /data1/ekyang/cgh/CODE/mht_work/e1e3] [--oat <patched OAT dir>] [--tokenizer <dir>]

Per candidate (model) step: token length (OAT serialisation + Qwen3 tokenizer, as e2_score.py), relative position,
has_code (``` or "def "/"import " in the step text). Reports, per dataset:
  - rank-AUROC of each covariate used as a scorer (both signs: longer / shorter);
  - within-trajectory Spearman of base - tapt with log length;
  - rank-AUROC of base - tapt after removing the covariates: OLS of the score on [log length, relative position, has_code]
    with trajectory fixed effects (all variables demeaned within trajectory), fitted WITHOUT labels; the residual is scored.
    Same for NLL_base and for OAT (seed-mean step scores, every proxy found), for reference.
  - paired bootstrap (1000) of selected differences (OAT tapt - base, scorers - "longer step"), raw and residual.
"""
import argparse, json, os, sys
import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(__file__))
import e1e3_analyze as EA   # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="/data1/ekyang/cgh/CODE/mht_work/e1e3")
    ap.add_argument("--oat", default=None); ap.add_argument("--tokenizer", default="/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B")
    a = ap.parse_args(); D = a.root; sys.path.insert(0, a.oat or os.path.join(D, "oat_src")); os.chdir(a.oat or os.path.join(D, "oat_src"))
    import data_pipeline as dp, extract_states as ex
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    T = EA.load_trajs(D)
    E2 = {n: {(r["dataset"], r["id"]): dict(zip(r["step_indices"], r["step_nll"])) for r in json.load(open(f"{D}/e2_scores_{n}.json"))["rows"]}
          for n in ("base", "tapt")}
    # OAT step scores, mean over the 5 seeds (rank-AUROC of the seed mean; the pre-registered table averages metrics instead)
    OAT = {}
    for proxy in ("base", "tapt", "S", "R"):
        acc = {}
        for ds in ("who_and_when", "traceelephant_gc"):
            for k5 in range(5):
                f = f"{D}/oat_{proxy}/outputs/results/ood/mcp_atlas_to_{ds}/OAT_coral/predictions_seed{k5}.json"
                if not os.path.exists(f): break
                for pr in json.load(open(f)):
                    for si, sc in zip(pr["score_step_indices"], pr["scores"]):
                        acc.setdefault((ds, pr["trajectory_id"]), {}).setdefault(si, []).append(sc)
        if acc: OAT[proxy] = {k: {si: float(np.mean(v)) for si, v in d.items()} for k, d in acc.items()}
    feats = {}
    for ds in ("who_and_when", "traceelephant_gc"):
        for t in dp.load_raw_trajectories(ds):
            k = (ds, t["id"])
            if k not in T: continue
            text, bounds = ex._build_input_text(t)
            enc = tok(text, return_offsets_mapping=True); rng = dp.get_step_token_ranges(enc["offset_mapping"], bounds)
            f = {}
            for j, ((s, e), (cs, ce)) in enumerate(zip(rng, bounds)):
                si = j - 1   # index 0 = question
                seg = text[cs:ce]
                f[si] = {"len": max(e - s + 1, 1), "code": float("```" in seg or "def " in seg or "import " in seg)}
            feats[k] = f
    out = {}; PER = {}   # PER[scorer][traj] = {"raw": rauc, "residual": rauc}
    for ds in ("who_and_when", "traceelephant_gc"):
        keys = [k for k in T if k[0] == ds and T[k]["mistake"] in T[k]["cand"] and len(T[k]["cand"]) >= 3 and k in feats]
        res = {"n": len(keys)}
        for nm, fn in {"longer": lambda k, c: feats[k][c]["len"], "shorter": lambda k, c: -feats[k][c]["len"],
                       "has_code": lambda k, c: feats[k][c]["code"]}.items():
            v = {k: EA.metrics_for({c: fn(k, c) for c in T[k]["cand"]}, T[k]["cand"], T[k]["mistake"])["rauc"] for k in keys}
            res["cov_" + nm] = float(np.mean(list(v.values())))
            for k, x in v.items(): PER.setdefault("cov_" + nm, {})[k] = {"raw": x, "residual": x}
        res["spearman_bmt_loglen"] = float(np.nanmean([spearmanr([np.log(feats[k][c]["len"]) for c in T[k]["cand"]],
                                                                 [E2["base"][k][c] - E2["tapt"][k][c] for c in T[k]["cand"]]).correlation for k in keys]))
        scorers = {"base_minus_tapt": lambda k, c: E2["base"][k][c] - E2["tapt"][k][c], "nll_base": lambda k, c: E2["base"][k][c]}
        for proxy in OAT:
            scorers[f"oat_{proxy}"] = (lambda P: (lambda k, c: OAT[P][k][c]))(proxy)
        for sname, sfn in scorers.items():
            Y, X, idx = [], [], []
            for k in keys:
                if sname.startswith("oat_") and (k not in OAT[sname[4:]] or any(c not in OAT[sname[4:]][k] for c in T[k]["cand"])): continue
                cand = T[k]["cand"]; n = len(cand); N = max(T[k]["n_steps"] - 1, 1)
                y = np.array([sfn(k, c) for c in cand]); x = np.array([[np.log(feats[k][c]["len"]), c / N, feats[k][c]["code"]] for c in cand])
                Y.append(y - y.mean()); X.append(x - x.mean(0)); idx.append((k, cand))
            beta, *_ = np.linalg.lstsq(np.vstack(X), np.concatenate(Y), rcond=None)
            ra = []
            for (k, cand), y, x in zip(idx, Y, X):
                rsd = y - x @ beta
                ra.append(EA.metrics_for(dict(zip(cand, rsd)), cand, T[k]["mistake"])["rauc"])
                PER.setdefault(sname, {})[k] = {"raw": EA.metrics_for({c: sfn(k, c) for c in cand}, cand, T[k]["mistake"])["rauc"], "residual": ra[-1]}
            res[f"{sname}_raw"] = float(np.mean([EA.metrics_for({c: sfn(k, c) for c in cand}, cand, T[k]["mistake"])["rauc"] for k, cand in idx]))
            res[f"{sname}_n"] = len(idx)
            res[f"{sname}_residual"] = float(np.mean(ra)); res[f"{sname}_beta_loglen_relpos_code"] = [float(b) for b in beta]
        out[ds] = res
    # paired bootstrap (1000, over trajectories) of selected differences, raw and residual
    rng = np.random.default_rng(0); pairs = [("oat_tapt", "oat_base"), ("oat_base", "cov_longer"), ("oat_tapt", "cov_longer"),
                                             ("base_minus_tapt", "cov_longer"), ("nll_base", "cov_longer")]
    for proxy in ("S", "R"):
        if f"oat_{proxy}" in PER: pairs += [(f"oat_{proxy}", "oat_base")]
    PER["chance"] = {k: {"raw": 0.5, "residual": 0.5} for k in PER["cov_longer"]}
    pairs += [(x, "chance") for x in ("base_minus_tapt", "oat_base", "oat_tapt", "oat_S", "oat_R")]
    out["paired"] = {}
    for x, y in pairs:
        if x not in PER or y not in PER: continue
        for sn, filt in (("WW", "who_and_when"), ("TEgc", "traceelephant_gc"), ("pooled", None)):
            ids = [k for k in PER[x] if k in PER[y] and (filt is None or k[0] == filt)]
            for kind in ("raw", "residual"):
                d = np.array([PER[x][k][kind] - PER[y][k][kind] for k in ids])
                bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(1000)]
                out["paired"][f"{x} - {y} / {sn} / {kind}"] = {"n": len(d), "diff": float(d.mean()),
                                                               "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
    print(json.dumps(out, indent=1)); json.dump(out, open(os.path.join(D, "e1e3_confounds.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
