"""Read-only Week 8 Josh Jacobs J2 receiving sensitivity; never modifies production."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_rb_model_j2 import features, priors, ols

root = Path("projection-model")
hist = pd.read_csv(root / "2025-historical-ppr-dataset.csv")
hist = hist.loc[hist.position.eq("RB") & hist.week.ge(7)].copy()
live = pd.read_csv(root / "validation/2026-live-rb-j2-features-audit.csv")
jacobs = live.loc[live.player_name.eq("Josh Jacobs") & live.team.eq("GB")].copy()
if len(jacobs) != 1 or int(jacobs.iloc[0].snapshot_week) != 8:
    raise ValueError("Expected one Week 8 Josh Jacobs row")
if int(jacobs.iloc[0].rb_season_games) != 1:
    raise ValueError("Jacobs sample changed; review scenarios before running")
p = priors(hist)
train_x = features(hist, p, "J2_RB_role_stability")
scenarios = [
    ("observed_5_catches_55yd", 7., 5., 55.),
    ("moderate_4_catches_35yd", 5., 4., 35.),
    ("lower_3_catches_25yd", 4., 3., 25.),
]
results = []
for label, targets, catches, yards in scenarios:
    row = jacobs.copy()
    for pg, season, value in [
        ("rb_targets_pg", "rb_season_targets", targets),
        ("rb_receptions_pg", "rb_season_receptions", catches),
        ("rb_receiving_yards_pg", "rb_season_receiving_yards", yards),
    ]:
        row[pg] = value
        row[season] = value  # exactly one recorded game
    prediction = float(ols(train_x, hist.actual_ppr, features(row, p, "J2_RB_role_stability"))[0])
    results.append(dict(scenario=label, targets=targets, receptions=catches,
                        receiving_yards=yards, j2_projected_ppr=round(prediction, 2)))
out = pd.DataFrame(results)
out["difference_from_observed"] = (out.j2_projected_ppr - out.j2_projected_ppr.iloc[0]).round(2)
print(out.to_string(index=False))
production = pd.read_csv(root / "2026-week8-ppr-projections.csv")
current = production.loc[production.player_name.eq("Josh Jacobs") & production.team.eq("GB")]
if len(current) != 1: raise ValueError("Production Jacobs row missing/duplicate")
print("Production Week 8 PPR:", current.iloc[0].projected_ppr, "Model:", current.iloc[0].projection_model)
print("READ ONLY. Scenario rows are hypothetical, not updated real workload. No production writes.")
