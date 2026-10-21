"""Read-only retrospective audit: 2025 TE PPR errors versus team personnel tendencies.

IMPORTANT: Personnel shares are FULL-SEASON 2025 aggregates and therefore
contain future information relative to weekly forecasts. This is descriptive
diagnostics only, NOT a leak-free backtest or basis for live model weights.
"""
import json
from pathlib import Path
import pandas as pd

PRED = Path("projection-model/2025-ppr-walkforward-predictions.csv")
SCHEME = Path("data/team_personnel_trends_2025.json")
OUT = Path("projection-model/validation/2025-te-personnel-descriptive-audit.csv")
pred = pd.read_csv(PRED)
personnel = json.loads(SCHEME.read_text(encoding="utf-8"))
assert personnel["season"] == 2025
teams = pd.DataFrame([
    {"team": x["team"], "two_plus_te_pct": x["two_plus_te_share_pct"],
     "personnel_12_pct": x["personnel_share_pct"]["12"],
     "personnel_13_pct": x["personnel_share_pct"]["13"]}
    for x in personnel["teams"]
])
te = pred.loc[(pred.position == "TE") & (pred.model == "F_position_specific")].copy()
if "team" not in te.columns:
    raise SystemExit("Historical predictions have no team column; cannot join personnel without a verified mapping.")
te["actual_ppr"] = pd.to_numeric(te["actual_ppr"], errors="coerce")
te["projected_ppr"] = pd.to_numeric(te["projected_ppr"], errors="coerce")
te = te.dropna(subset=["actual_ppr", "projected_ppr"])
te["team"] = te["team"].replace({"LAR":"LA"})
joined = te.merge(teams, on="team", how="inner", validate="many_to_one")
if len(joined) < 100:
    raise SystemExit(f"Only {len(joined)} TE records matched; inspect team naming and dataset.")
joined["absolute_error"] = (joined["actual_ppr"]-joined["projected_ppr"]).abs()
joined["signed_error"] = joined["actual_ppr"]-joined["projected_ppr"]
joined["two_plus_te_band"] = pd.cut(joined.two_plus_te_pct, [-1,25,35,45,101],
                                   labels=["<=25%","25-35%","35-45%",">45%"])
report = joined.groupby("two_plus_te_band", observed=True).agg(
    rows=("absolute_error","size"),
    mean_abs_error=("absolute_error","mean"),
    mean_signed_error=("signed_error","mean"),
    avg_actual_ppr=("actual_ppr","mean"),
    avg_projected_ppr=("projected_ppr","mean")
).reset_index()
OUT.parent.mkdir(parents=True,exist_ok=True)
report.to_csv(OUT,index=False)
print(report.to_string(index=False))
print("Joined rows:",len(joined),"of",len(te),"TE forecasts")
print("WARNING: Full-season personnel aggregates leak future games.")
print("DESCRIPTIVE ONLY. No live model edits or evidence of predictive improvement.")
print("For valid evaluation, build week-by-week personnel snapshots using only pregame plays.")
