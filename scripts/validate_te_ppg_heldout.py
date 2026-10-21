"""Held-out 2025 TE PPG blend audit. Read-only, no publishing."""
from pathlib import Path
import pandas as pd

SOURCE = Path("projection-model/2025-ppr-walkforward-predictions.csv")
OUT = Path("projection-model/validation/2025-te-ppg-heldout-validation.csv")
df = pd.read_csv(SOURCE)
df = df.loc[(df.position == "TE") & (df.model == "F_position_specific")].copy()
df["week"] = pd.to_numeric(df.week)
df["actual_ppr"] = pd.to_numeric(df.actual_ppr)
df["projected_ppr"] = pd.to_numeric(df.projected_ppr)
df = df.sort_values(["week", "player_id"])
# Prior-week only: the target week's actual result never enters its prediction.
prior = {}
records = []
for week, group in df.groupby("week", sort=True):
    for _, r in group.iterrows():
        history = prior.get(r.player_id, [])
        ppg = sum(history)/len(history) if len(history) >= 2 else None
        challenger = (r.projected_ppr + ppg)/2 if ppg is not None else r.projected_ppr
        records.append(dict(week=week, player_id=r.player_id, player_name=r.player_name,
                            actual_ppr=r.actual_ppr, baseline_ppr=r.projected_ppr,
                            prior_games=len(history), prior_ppg=ppg, challenger_ppr=challenger))
    for _, r in group.iterrows():
        prior.setdefault(r.player_id, []).append(r.actual_ppr)
out = pd.DataFrame(records)
# Historical walkforward predictions start at week 7; earlier actuals are absent.
# Therefore only evaluate later weeks after enough observed historical weeks exist.
out = out[out.week >= 10].copy()
out["baseline_rank"] = out.groupby("week").baseline_ppr.rank(method="min", ascending=False)
out["challenger_rank"] = out.groupby("week").challenger_ppr.rank(method="min", ascending=False)
out["actual_rank"] = out.groupby("week").actual_ppr.rank(method="min", ascending=False)
out["baseline_error"] = (out.actual_ppr - out.baseline_ppr).abs()
out["challenger_error"] = (out.actual_ppr - out.challenger_ppr).abs()
out["baseline_rank_error"] = (out.actual_rank - out.baseline_rank).abs()
out["challenger_rank_error"] = (out.actual_rank - out.challenger_rank).abs()
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False)
print("Held-out later weeks: 10+; blend fixed at 50%, no weight tuning")
print("Note: week 7-9 results populate prior history; weeks 1-6 are unavailable in this prediction file.")
for label, col, rank in [("Model F", "baseline_error", "baseline_rank_error"),
                         ("50% challenger", "challenger_error", "challenger_rank_error")]:
    print(f"{label}: rows={len(out)}, MAE={out[col].mean():.4f}, mean_rank_error={out[rank].mean():.3f}")
    for k in [12,24]:
        subset = out[out.actual_rank <= k]
        hits = (subset["baseline_rank" if label=="Model F" else "challenger_rank"] <= k).mean()
        print(f"  actual top-{k} recall={hits:.3%} (n={len(subset)})")
print(f"Saved {OUT}")
