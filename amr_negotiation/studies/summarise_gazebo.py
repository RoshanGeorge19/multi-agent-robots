"""Summarise the current-code Gazebo runs from report/gazebo_main_runs.csv (122 original cases) and
report/gazebo_all_runs.csv (all-study batch), both written by analyse_gazebo_main.py. Writes report/gazebo_all.md.

Delay is urgency-weighted; Gazebo delays use the 2D free-flow time of the same robot. Excess delay is against the
best forced yielder of the same simulator, so the Gazebo column needs the forced_A/forced_B Gazebo runs."""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
R = HERE / "report"
df = pd.concat([pd.read_csv(R / f) for f in ("gazebo_main_runs.csv", "gazebo_all_runs.csv") if (R / f).exists()])
out = []


def table(frame):
    out.append(frame.to_markdown(index=False, floatfmt=".1f"))
    out.append("")


g = df.groupby(["kind", "policy"])
s = pd.DataFrame({
    "n": g.size(), "Gazebo success": g.gz_success.sum(), "collisions": g.gz_collision.sum(),
    "2D success": g.d2_success.sum(), "same first yielder": g.apply(lambda v: (v.gz_yielder == v.d2_yielder).sum()),
    "delay Gazebo [s]": g.gz_wdelay.mean(), "delay 2D [s]": g.d2_wdelay.mean(),
    "Gazebo − 2D [s]": g.apply(lambda v: (v.gz_wdelay - v.d2_wdelay).mean()),
}).reset_index()
out.append(f"## All current-code Gazebo runs ({len(df)})\n")
table(s)
neg = df[df.policy != "reactive"]
out.append(f"All policies except reactive (negotiating and forced yielders): {int(neg.gz_collision.sum())} collisions "
           f"and {int((~neg.gz_success.astype(bool)).sum())} failures in {len(neg)} Gazebo runs.\n")

rows = []
for scen, v in df[df.scenario.str.match(r"gz_(s|urg_s|slow_s)\d+$")].groupby("scenario"):
    f = v.set_index("policy")
    if not {"forced_A", "forced_B"} <= set(f.index):
        continue
    ref_gz, ref_2d = min(f.loc["forced_A", "gz_wdelay"], f.loc["forced_B", "gz_wdelay"]), \
        min(f.loc["forced_A", "d2_wdelay"], f.loc["forced_B", "d2_wdelay"])
    for p, r in f.drop(["forced_A", "forced_B"]).iterrows():
        rows.append({"set": scen.rsplit("_s", 1)[0].replace("gz", "corridor").replace("corridor_", ""), "policy": p,
                     "gz": r.gz_wdelay - ref_gz, "d2": r.d2_wdelay - ref_2d})
if rows:
    e = pd.DataFrame(rows).groupby(["set", "policy"])
    out.append("## Excess delay over the best forced yielder of the same simulator\n")
    table(pd.DataFrame({"n": e.size(), "Gazebo [s]": e.gz.mean(), "2D [s]": e.d2.mean()}).reset_index())

x = df[df.kind.str.startswith("explore_")]
if len(x):
    g = x.groupby(["kind", "policy"])
    out.append("## Explore mode: map from the peer received before the first decision\n")
    table(pd.DataFrame({"n": g.size(), "Gazebo": g.gz_map_first.sum(), "2D": g.d2_map_first.sum(),
                        "detect dist. Gazebo [m]": g.gz_detect_dist.mean(), "detect dist. 2D [m]": g.d2_detect_dist.mean(),
                        "delay Gazebo [s]": g.gz_wdelay.mean(), "delay 2D [s]": g.d2_wdelay.mean()}).reset_index())
(R / "gazebo_all.md").write_text("\n".join(out))
print("\n".join(out))
