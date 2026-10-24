"""LLM negotiator study: does a local LLM pick the right yielder, and what does its thinking time cost?

Random two-robot encounters (same generator as the learned-negotiator study: random start delays, urgency,
loaded flags and bay positions, single- and two-bay corridors). For each encounter we run both forced outcomes
(the best forced yielder is the reference), the rulebook / fixed-priority / cost_bid baselines, and the LLM
variants. Excess delay = urgency-weighted total delay minus that of the best forced yielder.

Needs an OpenAI-compatible server, e.g. llama.cpp:  llama-server -m model.gguf --port 8080 --parallel 4
Run from amr_negotiation/:
  python studies/llm_negotiation.py --tag qwen7b --n 50
  -> studies/results_raw/llm/<tag>/{rows.jsonl,cache.jsonl,meta.json}, studies/report/llm_<tag>.md
Re-running with the same tag replays cached LLM answers, so an interrupted run resumes cheaply."""
import argparse
import json
import multiprocessing as mp
import os
import time
import urllib.request
from pathlib import Path

import numpy as np
from learned_negotiator import config, wdelay

from amr_negotiation import sim2d

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {"llm_med_raw": ("mediator", "raw", "none", ""), "llm_med_plans": ("mediator", "plans", "none", ""),
            "llm_agents_raw": ("agents", "raw", "none", ""), "llm_agents_plans": ("agents", "plans", "none", ""),
            "llm_med_img": ("mediator", "raw", "only", ""), "llm_med_imgtext": ("mediator", "raw", "both", ""),
            "llm_agents_img": ("agents", "raw", "ego", ""),
            "llm_agents_nonce": ("agents", "raw", "none", "nonce"),
            "llm_agents_img_nonce": ("agents", "raw", "ego", "nonce"),
            "llm_agents_silent": ("agents", "raw", "ego", "silent"),
            "llm_agents_commit": ("agents", "raw", "none", "commit"),
            "llm_agents_img_commit": ("agents", "raw", "ego", "commit"),
            "llm_agents_csilent": ("agents", "raw", "none", "csilent")}
BASELINES = {"fixed_priority": {"name": "fixed_priority"}, "rules_default": {"name": "rule_based"},
             "cost_bid": {"name": "cost_bid"}}
TIE = 0.5  # s: forced outcomes closer than this count as a tie (either yielder is right)


def policies(a):
    pols = dict(BASELINES)
    for v in a.variants:
        mode, info, vision, tb = VARIANTS[v]
        pols[v] = {"name": "llm", "llm": {"mode": mode, "info": info, "vision": vision, "tiebreak": tb,
                                          "base_url": a.base_url, "model": a.model,
                                          "think_time": a.think if a.think == "measured" else float(a.think),
                                          "max_tokens": a.max_tokens, "constrain": not a.no_constrain,
                                          "timeout": a.llm_timeout,
                                          "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}
                                                        if a.no_think else None,
                                          "cache": str(a.out / "cache.jsonl")}}
    return pols


def job(args):
    seed, layout, a = args
    sc = config(seed, layout)
    ids = sorted(x.id for x in sc.agents)
    forced = {i: wdelay(sim2d.run_episode(sc, {"name": "forced", "yielder": i}, seed=seed), sc) for i in ids}
    best = min(forced.values())
    gap = abs(forced[ids[0]] - forced[ids[1]])
    best_y = "tie" if gap < TIE else min(forced, key=forced.get)
    rows = []
    for label, pol in policies(a).items():
        if pol["name"] == "llm":
            pol = {**pol, "llm": {**pol["llm"], "draw_seed": seed}}  # commit-reveal nonces keyed per encounter
        r = sim2d.run_episode(sc, pol, seed=seed)
        d = r["decisions"][0] if r["decisions"] else {}
        rule = d.get("rule") or ""
        rows.append({"label": label, "layout": layout, "seed": seed, "success": r["success"],
                     "collision": r["collision"], "deadlock": r["deadlock"], "wdelay": wdelay(r, sc),
                     "excess": wdelay(r, sc) - best, "makespan": r["makespan"], "yielder": d.get("yielder"),
                     "best_yielder": best_y, "forced_gap": gap, "rule": rule,
                     "fallback": rule.split(":")[0].removeprefix("llm_fallback_") if rule.startswith("llm_fallback") else None,
                     "think_time": d.get("think_time", 0.0), "llm_error": d.get("llm_error"),
                     "llm_answers": d.get("llm_answers"), "llm_tiebreak": d.get("llm_tiebreak")})
    return rows


def ci95(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def report(rows, a, meta):
    labels = list(BASELINES) + a.variants
    out = [f"# LLM negotiator study: `{a.tag}`", "",
           (f"Model `{a.model}` at `{a.base_url}` (server reports: {meta.get('server_models')}). "
           f"{a.n} encounters per layout ({', '.join(a.layouts)}), think time `{a.think}`, "
           f"constrained JSON {'off' if a.no_constrain else 'on'}. Generated by `studies/llm_negotiation.py` "
           f"in {meta['wall_s']:.0f} s."), "",
           ("Excess = urgency-weighted delay minus the best forced yielder's (s, mean ± 95% CI). "
           f"Right yielder: share of non-tie encounters (forced outcomes differ by ≥ {TIE} s) where the first "
           "decision named the better yielder. Fallback: the LLM answer was not used (error / parse / disagree / "
           "infeasible) and the rulebook decided."), "",
           "| policy | runs | success | collisions | excess (s) | right yielder | fallback | think (s) |",
           "|---|---|---|---|---|---|---|---|"]
    for lab in labels:
        rs = [r for r in rows if r["label"] == lab]
        if not rs:
            continue
        ok = [r for r in rs if r["success"]]
        nt = [r for r in rs if r["best_yielder"] != "tie" and r["yielder"]]
        right = f"{np.mean([r['yielder'] == r['best_yielder'] for r in nt]):.0%}" if nt else "–"
        fb = [r["fallback"] for r in rs if r["fallback"]]
        kinds = ", ".join(f"{k} {fb.count(k)}" for k in sorted(set(fb)))
        fbs = f"{len(fb) / len(rs):.0%}" + (f" ({kinds})" if kinds else "") if lab.startswith("llm") else "–"
        ex = [r["excess"] for r in ok]
        think = f"{np.mean([r['think_time'] for r in rs]):.1f}" if lab.startswith("llm") else "–"
        out.append(f"| `{lab}` | {len(rs)} | {len(ok) / len(rs):.0%} | {sum(r['collision'] for r in rs)} | "
                   f"{np.mean(ex):.1f} ± {ci95(ex):.1f} | {right} | {fbs} | {think} |")
    out += ["", "Per layout, mean excess (s):", "", "| policy | " + " | ".join(a.layouts) + " |",
            "|---|" + "---|" * len(a.layouts)]
    for lab in labels:
        cells = []
        for lay in a.layouts:
            ex = [r["excess"] for r in rows if r["label"] == lab and r["layout"] == lay and r["success"]]
            cells.append(f"{np.mean(ex):.1f}" if ex else "–")
        out.append(f"| `{lab}` | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def server_models(base_url):
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=5) as r:
            return [m.get("id") for m in json.loads(r.read()).get("data", [])]
    except Exception as ex:  # noqa: BLE001 - provenance only
        return f"unavailable ({type(ex).__name__})"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="name for this run, e.g. the model (qwen7b)")
    ap.add_argument("--model", default=os.environ.get("AMRNEG_LLM_MODEL", "local"))
    ap.add_argument("--base-url", default=os.environ.get("AMRNEG_LLM_URL", "http://localhost:8080/v1"))
    ap.add_argument("--n", type=int, default=50, help="encounters per layout")
    ap.add_argument("--layouts", nargs="+", default=["single_bay", "two_bays"])
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    ap.add_argument("--think", default="measured", help="'measured' (charge real LLM latency) or seconds, e.g. 0")
    ap.add_argument("--max-tokens", type=int, default=256, help="raise (e.g. 4096) for reasoning models")
    ap.add_argument("--llm-timeout", type=float, default=300.0, help="per-call timeout (s)")
    ap.add_argument("--no-think", action="store_true", help="disable reasoning traces (enable_thinking=false)")
    ap.add_argument("--no-constrain", action="store_true", help="don't send a JSON schema (older servers)")
    ap.add_argument("--workers", type=int, default=2, help="parallel episodes; match llama-server --parallel")
    ap.add_argument("--seed0", type=int, default=100_000, help="first encounter seed (held out from training)")
    a = ap.parse_args(argv)
    a.out = ROOT / "studies" / "results_raw" / "llm" / a.tag
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = [(a.seed0 + i, lay, a) for lay in a.layouts for i in range(a.n)]
    t0, rows = time.time(), []
    with mp.Pool(a.workers) as pool:
        for k, rs in enumerate(pool.imap_unordered(job, jobs), 1):
            rows += rs
            if k % 10 == 0 or k == len(jobs):
                print(f"{k}/{len(jobs)} encounters, {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=lambda r: (r["layout"], r["seed"], r["label"]))
    meta = {"tag": a.tag, "model": a.model, "base_url": a.base_url, "server_models": server_models(a.base_url),
            "n": a.n, "layouts": a.layouts, "variants": a.variants, "think": a.think, "max_tokens": a.max_tokens,
            "constrain": not a.no_constrain, "seed0": a.seed0, "wall_s": time.time() - t0}
    with open(a.out / "rows.jsonl", "w") as f:
        f.writelines(json.dumps(r, default=str) + "\n" for r in rows)
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1))
    rep = ROOT / "studies" / "report" / f"llm_{a.tag}.md"
    rep.write_text(report(rows, a, meta))
    print(rep.read_text())


if __name__ == "__main__":
    main()
