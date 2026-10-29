"""Round 76: training-process figures for the mid-training / fine-tuning runs (no new training, logs only).

  python scripts/plot_training_curves.py [--data results/figures/training_curves_data.json] [--out results/figures]

Data = the runs' own logs, collected on Linux #2 and copied verbatim (rounded to 5 decimals):
  tapt   mht_work/midtrain/tapt_pilot_v1/ckpt/logging.jsonl   (MS-Swift `swift pt`, LoRA r64, 24.5M tokens, 506 steps)
  e2_S   mht_work/e1e3/e2_S/ckpt/logging.jsonl              (same recipe, successful runs only, 6.06M tokens)
  e2_R   mht_work/e1e3/e2_R/ckpt/logging.jsonl              (same recipe, all outcomes, 6.09M tokens)
  samt   mht_work/midtrain/samt_v1/ckpt/logging.jsonl       (frozen Qwen3-8B; HGFM encoder + projector; answer-token loss)
  beft_* mht_work/e4/beft_{base,tapt}/log.jsonl             (BEFT on TracerTraj; CE over candidate steps)
  probe_* mht_work/e4/stageA/e4a_{linear,mlp}.json train_log  (frozen features; val rank-AUROC per epoch, 3 seeds;
          the log holds the base, tapt, S, R blocks in that order -- the --feats order of linux2_run_e4.sh)
train rows: [step, loss, token_acc, lr, grad_norm]; eval rows: [step, eval_loss, eval_token_acc].
"""
import argparse, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker

# reference categorical palette (dataviz skill, light mode), slots 1-3 in fixed order
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
                     "axes.titlesize": 10, "axes.titleweight": "bold", "savefig.dpi": 200, "figure.facecolor": "#fcfcfb",
                     "axes.facecolor": "#fcfcfb"})


def ema(y, a=0.2):
    out, s = [], None
    for v in y: s = v if s is None else a * v + (1 - a) * s; out.append(s)
    return np.array(out)


def tr(d, k):
    t = d[k]["train"]; return (np.array([float(r[0]) for r in t]), np.array([r[1] for r in t]), np.array([r[2] for r in t]),
                               np.array([r[4] for r in t]))


def save(fig, out, name):
    for ext in ("png", "pdf"): fig.savefig(os.path.join(out, f"{name}.{ext}"), bbox_inches="tight")
    plt.close(fig)


def fig_text_mt(d, out):
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.2))
    runs = (("tapt", "TAPT pilot v1 (24.5M tok, all sources)", C1), ("e2_S", "E2-S (6.1M tok, successful runs)", C2),
            ("e2_R", "E2-R (6.1M tok, all outcomes)", C3))
    for k, lab, c in runs:
        s, l, a, g = tr(d, k); ev = d[k]["eval"][0]
        ax[0].plot(s, l, color=c, lw=0.8, alpha=0.30); ax[0].plot(s, ema(l), color=c, lw=2, label=lab)
        ax[0].scatter([float(ev[0])], [ev[1]], color=c, s=40, marker="D", edgecolor="#fcfcfb", lw=1.5, zorder=5)
        ax[1].plot(s, a, color=c, lw=0.8, alpha=0.30); ax[1].plot(s, ema(a), color=c, lw=2)
        ax[1].scatter([float(ev[0])], [ev[2]], color=c, s=40, marker="D", edgecolor="#fcfcfb", lw=1.5, zorder=5)
        ax[2].plot(s / s.max(), ema(l), color=c, lw=2)
    ax[0].set(title="(a) LM loss", xlabel="optimizer step", ylabel="next-token CE (nats)")
    ax[1].set(title="(b) token accuracy", xlabel="optimizer step", ylabel="accuracy")
    ax[2].set(title="(c) loss vs fraction of the epoch", xlabel="fraction of the single epoch", ylabel="EMA loss")
    ax[0].legend(loc="upper right", fontsize=7.5)
    ax[0].text(0.98, 0.55, "thin = logged, thick = EMA(0.2)\n◆ = held-out loss at the end", transform=ax[0].transAxes,
               ha="right", fontsize=7, color=INK2)
    fig.suptitle("Text mid-training of Qwen3-8B (MS-Swift continued pre-training, LoRA r64 all-linear, 1 epoch)",
                 fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(); save(fig, out, "fig_tr1_text_midtraining")


def fig_samt(d, out):
    s, l, a, g = tr(d, "samt")
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.2))
    ax[0].plot(s, l, color=C1, lw=0.8, alpha=0.30); ax[0].plot(s, ema(l), color=C1, lw=2); ax[0].set_yscale("log")
    ax[0].set(title="(a) answer-token loss (log)", xlabel="optimizer step", ylabel="CE on answer tokens")
    ax[1].plot(s, a, color=C1, lw=0.8, alpha=0.30); ax[1].plot(s, ema(a), color=C1, lw=2)
    ax[1].set(title="(b) answer-token accuracy", xlabel="optimizer step", ylabel="accuracy")
    ax[2].plot(s, g, color=C1, lw=1.2); ax[2].set_yscale("log")
    ax[2].set(title="(c) gradient norm (log)", xlabel="optimizer step", ylabel="‖g‖ (pre-clip)")
    for x in ax: x.axvline(375, color=INK2, lw=0.8, ls=":")
    ax[1].text(380, 0.80, "epoch 2", fontsize=7, color=INK2)
    fig.suptitle("SAMT v1: frozen Qwen3-8B, HGFM v0.2 encoder + projector trained on O1-O4 graph-token questions "
                 "(19.1M trainable)", fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(); save(fig, out, "fig_tr2_samt")


def fig_beft(d, out):
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.2))
    for k, lab, c in (("beft_base", "init = Qwen3-8B", C1), ("beft_tapt", "init = TAPT pilot v1", C2)):
        L = [r for r in d[k] if "loss" in r]; V = [r for r in d[k] if "val_rauc" in r]
        s = np.array([r["opt_step"] for r in L]); l = np.array([r["loss"] for r in L])
        ax[0].plot(s, l, color=c, lw=0.8, alpha=0.30); ax[0].plot(s, ema(l, 0.15), color=c, lw=2, label=lab)
        vs = [(r["epoch"] * 1304 + r["at"]) / 16 for r in V]
        ax[1].plot(vs, [r["val_rauc"] for r in V], color=c, lw=2, marker="o", ms=6, mec="#fcfcfb", mew=1.5, label=lab)
        ax[2].plot(s, [r["bv_norm"] for r in L], color=c, lw=2)
    ax[0].set(title="(a) training loss", xlabel="optimizer step (16 traj. x 4 GPUs)",
              ylabel="CE over candidate steps")
    ax[0].text(0.98, 0.92, "per-log value = 1 trajectory (noisy);\nthick = EMA(0.15)", transform=ax[0].transAxes,
               ha="right", va="top", fontsize=7, color=INK2)
    ax[1].set(title="(b) TracerTraj val rank-AUROC", xlabel="optimizer step", ylabel="within-trajectory rank-AUROC")
    ax[1].legend(loc="lower right", fontsize=7.5)
    ax[2].set(title="(c) ‖b_v‖ (all 36 layers)", xlabel="optimizer step", ylabel="L2 norm of injected biases")
    fig.suptitle("E4 stage B: BEFT (36 x 1,024 value-projection biases + LN/linear head, ~49k trainable) on TracerTraj, 2 epochs",
                 fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(); save(fig, out, "fig_tr3_beft")


def split_blocks(log):
    """train_log = base, tapt, S, R blocks, each seeds 0,1,2 in order; a new block starts when seed goes 2 -> 0."""
    blocks, cur, prev = [], [], None
    for r in log:
        if prev == 2 and r["seed"] == 0: blocks.append(cur); cur = []
        cur.append(r); prev = r["seed"]
    blocks.append(cur); assert len(blocks) == 4, len(blocks); return blocks


def fig_probe(d, out):
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    for i, kind in enumerate(("linear", "mlp")):
        for blk, lab, c in zip(split_blocks(d[f"probe_{kind}"])[:2], ("features = Qwen3-8B", "features = TAPT pilot v1"), (C1, C2)):
            for sd in (0, 1, 2):
                rr = [r for r in blk if r["seed"] == sd]
                ax[i].plot([r["epoch"] + 1 for r in rr], [r["val_rauc"] for r in rr], color=c, lw=1.6,
                           ls=("-", "--", ":")[sd], label=lab if sd == 0 else None)
        ax[i].set(title=f"({'ab'[i]}) {kind} head", xlabel="epoch (early stop on val)")
    for x in ax: x.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax[0].set_ylabel("TracerTraj val rank-AUROC"); ax[0].legend(loc="lower right", fontsize=7.5)
    ax[1].text(0.98, 0.06, "line style = seed 0 / 1 / 2", transform=ax[1].transAxes, ha="right", fontsize=7, color=INK2)
    fig.suptitle("E4 stage A: heads on frozen step features (mean last-layer state over the step's tokens)",
                 fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(); save(fig, out, "fig_tr4_probe")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="results/figures/training_curves_data.json")
    ap.add_argument("--out", default="results/figures"); a = ap.parse_args(); d = json.load(open(a.data))
    for f in (fig_text_mt, fig_samt, fig_beft, fig_probe): f(d, a.out)
    # numbers quoted in the README
    for k in ("tapt", "e2_S", "e2_R", "samt"):
        s, l, ac, g = tr(d, k)
        print(k, "first", round(l[0], 3), "last10 mean", round(l[-10:].mean(), 3), "acc first/last10", round(ac[0], 3),
              round(ac[-10:].mean(), 3), "eval", d[k]["eval"][:1])
    for k in ("beft_base", "beft_tapt"):
        print(k, [round(r["val_rauc"], 3) for r in d[k] if "val_rauc" in r], "bv_norm end",
              [round(r["bv_norm"], 2) for r in d[k] if "loss" in r][-1])
    for kind in ("linear", "mlp"):
        for nm, blk in zip(("base", "tapt", "S", "R"), split_blocks(d[f"probe_{kind}"])):
            print(kind, nm, {sd: (max(r["val_rauc"] for r in blk if r["seed"] == sd).__round__(3),
                                  sum(1 for r in blk if r["seed"] == sd)) for sd in (0, 1, 2)})
