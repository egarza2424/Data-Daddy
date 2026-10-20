"""Compare frozen AI rankings and PPR-projection rankings against completed actuals.

Only matched player IDs with recorded actual PPR are scored. Never changes model outputs.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

CUTOFFS = {"QB": 24, "RB": 36, "WR": 36, "TE": 24}
OUT = Path("model-validation/ai-vs-ppr-ranking-audit.csv")

def evaluate(week):
    actual_path = Path(f"model-validation/2026-week{week}-validation.csv")
    projection_path = Path(f"projection-model/2026-week{week}-ppr-projections.csv")
    if not actual_path.exists() or not projection_path.exists():
        raise FileNotFoundError(f"Completed validation and frozen PPR projections required for week {week}")
    actual = pd.read_csv(actual_path, dtype={"player_id": str})
    projections = pd.read_csv(projection_path, dtype={"player_id": str})
    required_actual = {"player_id", "position", "position_rank", "actual_ppr"}
    required_proj = {"player_id", "position", "projected_position_rank"}
    if not required_actual.issubset(actual.columns) or not required_proj.issubset(projections.columns):
        raise ValueError("Missing required comparison columns")
    actual = actual[list(required_actual)].copy()
    projections = projections[list(required_proj)].copy()
    actual["actual_ppr"] = pd.to_numeric(actual.actual_ppr, errors="coerce")
    actual["position_rank"] = pd.to_numeric(actual.position_rank, errors="coerce")
    projections["projected_position_rank"] = pd.to_numeric(projections.projected_position_rank, errors="coerce")
    actual = actual.dropna(subset=["actual_ppr", "position_rank"])
    projections = projections.dropna(subset=["projected_position_rank"])
    if actual.duplicated(["player_id", "position"]).any() or projections.duplicated(["player_id", "position"]).any():
        raise ValueError("Duplicate player/position rows; audit requires unambiguous player matching")
    cohort = actual.merge(projections, on=["player_id", "position"], how="inner", validate="one_to_one")
    results = []
    for position, cutoff in CUTOFFS.items():
        group = cohort[cohort.position == position].copy()
        if group.empty:
            continue
        # Consistent tie-breakers across both models and actuals.
        actual_sorted = group.sort_values(["actual_ppr", "player_id"], ascending=[False, True])
        actual_rank = {pid: i + 1 for i, pid in enumerate(actual_sorted.player_id)}
        actual_top = set(actual_sorted.head(cutoff).player_id)
        for model, column in [("AI Rankings", "position_rank"), ("PPR Projection Rankings", "projected_position_rank")]:
            ordered = group.sort_values([column, "player_id"])
            selected = ordered.head(cutoff)
            hits = sum(pid in actual_top for pid in selected.player_id)
            n = len(selected)
            rank_error = np.mean([abs(i + 1 - actual_rank[pid]) for i, pid in enumerate(ordered.player_id)])
            results.append({
                "season": 2026, "week": week, "position": position, "model": model,
                "cutoff": cutoff, "matched_players": len(group), "evaluated_picks": n,
                "top_group_hits": hits, "top_group_accuracy_pct": round(100 * hits / n, 2),
                "mean_absolute_rank_error": round(float(rank_error), 4),
                "scope": "matched_cohort_only",
            })
    if not results:
        raise ValueError("No matched player results")
    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=None, help="Completed week; omit to audit all available completed weeks")
    args = parser.parse_args()
    weeks = [args.week] if args.week else sorted(int(p.stem.split("-week")[1].split("-")[0]) for p in Path("model-validation").glob("2026-week*-validation.csv") if "-week" in p.stem)
    frames = []
    for week in weeks:
        if not Path(f"projection-model/2026-week{week}-ppr-projections.csv").exists():
            print(f"Skipping Week {week}: no frozen PPR projection file")
            continue
        frames.append(evaluate(week))
    if not frames:
        raise ValueError("No completed weeks with both ranking models available")
    result = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result.to_string(index=False))
    print("Saved", OUT)

if __name__ == "__main__":
    main()
