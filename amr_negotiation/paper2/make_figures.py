#!/usr/bin/env python3
"""Paper 2 figures from studies/results_raw/llm/*/rows.jsonl."""
import json
import statistics as st
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1] / "studies" / "results_raw" / "llm"
FIG = Path(__file__).parent / "fig"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 8, "figure.dpi": 150})


def rows(tag):
    p = ROOT / tag / "rows.jsonl"
    return [json.loads(l) for l in open(p)] if p.exists() else []


def stat(tag, label, key="excess"):
    xs = [r[key] for r in rows(tag) if r["label"] == label and r["success"]]
    return (st.mean(xs), st.stdev(xs) / max(len(xs) - 1, 1) ** 0.5 * 1.96) if xs else (None, None)


def barset(groups, path, ylab, title=None, ylim=None, refs=None):
    """groups: list of (label, [ (xlabel, mean, err) ]) -> grouped bars."""
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    n = len(groups)
    w = 0.8 / n
    xs = sorted({x for _, es in groups for x, _, _ in es})
    pos = {x: i for i, x in enumerate(xs)}
    for gi, (gl, es) in enumerate(groups):
        for x, m, e in es:
            if m is None:
                continue
            ax.bar(pos[x] + (gi - (n - 1) / 2) * w, m, w * 0.9, yerr=e, label=gl if pos[x] == 0 else None,
                   capsize=2)
    ax.set_xticks(list(pos.values()))
    ax.set_xticklabels(xs, rotation=30, ha="right")
    ax.set_ylabel(ylab)
    if title:
        ax.set_title(title, fontsize=8)
    if ylim:
        ax.set_ylim(*ylim)
    ax.axhline(0, color="k", lw=0.5)
    if n > 1:
        ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


# ---- fig_screen: screen excess by model vs baselines
models = [("qwen3.8-27b", "Qwen3.8-27B"), ("qwen3-30b", "Qwen3-30B"), ("nemotron-3-super", "N3-Super"),
          ("nemotron-nano", "N3-Nano"), ("nemotron-omni", "N3-Omni"), ("nemotron-lightning", "N3.5-Light"),
          ("gemma4-26b", "Gemma4-26B"), ("nemotron-super-49b", "N-Super49"), ("nemotron-vl-12b", "N-VL-12B"),
          ("muse-glimmer", "MuseGlm")]
es = [(name, *stat(tag, "llm_med_plans")) for tag, name in models]
groups = [("LLM med_plans", es),
          ("cost_bid", [("cost_bid", *stat("nemotron-nano", "cost_bid"))]),
          ("rulebook", [("rulebook", *stat("nemotron-nano", "rules_default"))]),
          ("fixed_prio", [("fixed_prio", *stat("nemotron-nano", "fixed_priority"))])]
barset(groups, "screen.pdf", "excess delay (s)")

# ---- fig_think: reasoning on/off (med variants), qwen3.8 + qwen3-30b
groups = []
for tag, name in [("qwen3.8-27b", "Q3.8"), ("qwen3-30b", "Q3-30B")]:
    groups.append((name, [
        (f"{name} raw off", *stat(tag + "-off0", "llm_med_raw")),
        (f"{name} plans off", *stat(tag + "-off0", "llm_med_plans")),
        (f"{name} raw on", *stat(tag + "-on0", "llm_med_raw")),
        (f"{name} plans on", *stat(tag + "-on0", "llm_med_plans"))]))
barset(groups, "think.pdf", "excess delay (s)")

# ---- fig_latency: quality (think=0) vs measured excess, med_plans
groups = [("quality only", [(t, *stat(t + "-off0" if t != "nemotron-3-super" else t + "-off0", "llm_med_plans"))
                            for t in ["qwen3.8-27b", "qwen3-30b"]]),
          ("measured", [("qwen3.8-27b", *stat("qwen3.8-27b-offm-s", "llm_med_plans")),
                        ("qwen3.8-27b ", *stat("qwen3.8-27b-on0", "llm_med_plans")),
                        ("qwen3-30b", *stat("qwen3-30b-offm-s", "llm_med_plans")),
                        ("qwen3-30b ", *stat("qwen3-30b-onm", "llm_med_plans"))])]
barset(groups, "latency.pdf", "excess delay (s)")

# ---- fig_vlm: modality arms per VL model
groups = [("text", [(t, *stat(t + "-vlm", "llm_med_plans")) for t in
                    ["gemma4-26b", "nemotron-omni", "nemotron-vl-12b", "qwen3.8-27b"]]),
          ("image", [(t, *stat(t + "-vlm", "llm_med_img")) for t in
                     ["gemma4-26b", "nemotron-omni", "nemotron-vl-12b", "qwen3.8-27b"]]),
          ("text+image", [(t, *stat(t + "-vlm", "llm_med_imgtext")) for t in
                          ["gemma4-26b", "nemotron-omni", "nemotron-vl-12b", "qwen3.8-27b"]])]
barset(groups, "vlm.pdf", "excess delay (s)")

# ---- fig_disagree: action-agreement modes, ego arm
fig, ax = plt.subplots(figsize=(3.45, 2.1))
tags = ["gemma4-26b-ego", "qwen3.8-27b-ego", "nemotron-omni-ego", "nemotron-vl-12b-ego"]
names = ["Gemma4", "Q3.8", "N-Omni", "N-VL12B"]
modes = {"agree": ("proceed", "yield"), "both yield": ("yield", "yield"), "both proceed": ("proceed", "proceed")}
colors = {"agree": "tab:green", "both yield": "tab:blue", "both proceed": "tab:red"}
bottom = [0] * len(tags)
for m, acts in modes.items():
    vals = []
    for tag in tags:
        c = Counter()
        for r in rows(tag):
            if r["label"] == "llm_agents_img" and r.get("llm_answers"):
                c[tuple(sorted(a.get("action", "?") for a in r["llm_answers"]))] += 1
        tot = sum(c.values()) or 1
        vals.append(c.get(acts, 0) / tot * 100)
    ax.bar(names, vals, 0.6, bottom=bottom, label=m, color=colors[m])
    bottom = [b + v for b, v in zip(bottom, vals)]
ax.set_ylabel("% of encounters")
ax.legend(fontsize=6, frameon=False)
fig.tight_layout()
fig.savefig(FIG / "disagree.pdf", bbox_inches="tight")
plt.close(fig)
print("wrote disagree.pdf")

# ---- fig_tiebreak: triad (img=rulebook, silent=hidden draw, nonce=visible draw)
groups = [("excess", []), ("right yielder", [])]
for tag in ["gemma4-26b", "qwen3.8-27b", "nemotron-omni", "nemotron-vl-12b"]:
    rs_img = [r for r in rows(tag + "-silent") if r["label"] == "llm_agents_img"]
    rs_sil = [r for r in rows(tag + "-silent") if r["label"] == "llm_agents_silent"]
    rs_non = [r for r in rows(tag + "-nonce") if r["label"] == "llm_agents_img_nonce"]
    for i, rs in enumerate([rs_img, rs_sil, rs_non]):
        if rs:
            groups[0][1].append((f"{tag.split('-')[0]}-{'rule' if i==0 else 'hide' if i==1 else 'vis'}",
                                 st.mean([r["excess"] for r in rs]), 0))
barset([groups[0]], "tiebreak.pdf", "excess delay (s)")
