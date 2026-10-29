"""Read-only Josh Jacobs Week 8 J2 full-workload sensitivity."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_rb_model_j2 import features, priors, ols

root=Path("projection-model")
hist=pd.read_csv(root/"2025-historical-ppr-dataset.csv")
hist=hist.loc[hist.position.eq("RB") & hist.week.ge(7)].copy()
live=pd.read_csv(root/"validation/2026-live-rb-j2-features-audit.csv")
row=live.loc[live.player_name.eq("Josh Jacobs") & live.team.eq("GB")].copy()
if len(row)!=1 or int(row.iloc[0].snapshot_week)!=8 or int(row.iloc[0].rb_season_games)!=1:
    raise ValueError("Expected one Week 8 Jacobs row with one recorded game")
p=priors(hist)
x=features(hist,p,"J2_RB_role_stability")
# Carries, rushing yards, targets, receptions, receiving yards. Historical 2025 averages:
# 234/15=15.6, 929/15=61.933, 44/15=2.933, 36/15=2.4, 282/15=18.8
cases=[
 ("observed_2026",11,36,7,5,55),
 ("historical_2025",15.6,929/15,44/15,36/15,282/15),
 ("historical_rush_moderate_rec",15.6,929/15,5,4,35),
 ("historical_rush_lower_rec",15.6,929/15,4,3,25),
 ("moderate_rush_historical_rec",14,55,44/15,36/15,282/15),
]
out=[]
for name,carries,rush,targets,receptions,receiving in cases:
    test=row.copy()
    for recent,season,value in [
      ("rb_carries_pg","rb_season_carries",carries),
      ("rb_rush_yards_pg","rb_season_rush_yards",rush),
      ("rb_targets_pg","rb_season_targets",targets),
      ("rb_receptions_pg","rb_season_receptions",receptions),
      ("rb_receiving_yards_pg","rb_season_receiving_yards",receiving),
    ]:
        test[recent]=value
        test[season]=value
    value=float(ols(x,hist.actual_ppr,features(test,p,"J2_RB_role_stability"))[0])
    out.append(dict(scenario=name,carries=round(carries,2),rush_yards=round(rush,2),
                    targets=round(targets,2),receptions=round(receptions,2),
                    receiving_yards=round(receiving,2),j2_ppr=round(value,2)))
result=pd.DataFrame(out)
result["delta_vs_production"]=(result.j2_ppr-19.18).round(2)
print(result.to_string(index=False))
print("NOTE: Red-zone carries/targets, team total, and one-game sample size held fixed.")
print("READ ONLY: No production files or model weights modified.")
