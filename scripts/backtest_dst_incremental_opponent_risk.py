#!/usr/bin/env python3
"""Read-only 2024-25 D/ST challenger: incremental opponent sack/INT vulnerability.
Uses frozen V1 prediction CSVs and prior-week nflverse offensive plays only.
No changes to production models, weights, rankings or projections.
"""
import collections,csv,json,math,pathlib
import duckdb

ROOT=pathlib.Path("projection-model/validation")
FILES={2024:ROOT/"dst_2024_fixed_2025_challenger_predictions.csv",
       2025:ROOT/"dst_2025_feature_challenger_predictions.csv"}
for year,path in FILES.items():
 if not path.exists():raise SystemExit(f"Missing {path}; run the {year} D/ST backtest first.")
def mean(v):return sum(v)/len(v) if v else 0.0
all_results={}
for season,path in FILES.items():
 with path.open(newline="") as f:baseline_rows=list(csv.DictReader(f))
 # nflverse game-by-game offense dropbacks, sacks allowed, interceptions.
 url=f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
 db=duckdb.connect()
 plays=db.execute("""SELECT week,game_id,play_id,posteam,
 COALESCE(qb_dropback,0),COALESCE(pass_attempt,0),
 COALESCE(sack,0),COALESCE(interception,0)
 FROM read_parquet(?) WHERE season=? AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL AND posteam IS NOT NULL
 AND (COALESCE(qb_dropback,0)=1 OR COALESCE(pass_attempt,0)=1 OR COALESCE(sack,0)=1 OR COALESCE(interception,0)=1)""",[url,season]).fetchall()
 schedule_rows=db.execute("SELECT DISTINCT week,home_team,away_team FROM read_parquet(?) WHERE season=? AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL",[url,season]).fetchall()
 opponents={}
 for w,home,away in schedule_rows:
  for defense,opponent in ((home,away),(away,home)):
   key=(int(w),defense)
   if key in opponents and opponents[key]!=opponent:raise SystemExit(f"Conflicting schedule: {key}")
   opponents[key]=opponent
 grouped=collections.defaultdict(lambda:collections.Counter())
 seen=set()
 for w,g,p,t,drop,pa,sack,inter in plays:
  k=(g,p)
  if k in seen:continue
  seen.add(k)
  c=grouped[(int(w),t)]
  c["dropbacks"]+=int(drop==1 or pa==1 or sack==1)
  c["sacks"]+=int(sack==1)
  c["ints"]+=int(inter==1)
 weekly=collections.defaultdict(list)
 for (w,t),c in grouped.items():weekly[w].append((t,c))
 predictions=collections.defaultdict(list)
 for r in baseline_rows:predictions[int(r["week"])].append(r)
 history=collections.defaultdict(lambda:collections.Counter())
 audit=[]
 for week in range(1,19):
  league=collections.Counter()
  for c in history.values():league.update(c)
  global_sack=league["sacks"]/league["dropbacks"] if league["dropbacks"] else 0.
  global_int=league["ints"]/league["dropbacks"] if league["dropbacks"] else 0.
  for r in predictions[week]:
   opp=opponents.get((week,r["defense"]))
   if not opp:raise SystemExit(f"Missing schedule opponent: {season} W{week} {r[\"defense\"]}")
   c=history[opp]
   if c["dropbacks"]<100 or league["dropbacks"]<1000:
    raise SystemExit(f"Insufficient prior-week offense history: {season} W{week} {opp}")
   # Shrink opponent sack and INT rates toward historical league averages;
   # 150 prior dropbacks stabilizes small-sample estimates.
   sack=(c["sacks"]+150*global_sack)/(c["dropbacks"]+150)
   inter=(c["ints"]+150*global_int)/(c["dropbacks"]+150)
   v1=float(r["all"]);actual=float(r["actual"])
   # Fixed, explicitly exploratory sensitivity coefficients in fantasy points
   # per percentage-point difference from league baseline.
   ds=100*(sack-global_sack);di=100*(inter-global_int)
   audit.append({"season":season,"week":week,"defense":r["defense"],
      "opponent":opp,"actual":actual,"v1":v1,
      "opponent_sack_rate_pct":round(100*sack,4),
      "opponent_int_rate_pct":round(100*inter,4),
      "sack_rate_delta_pp":round(ds,4),"int_rate_delta_pp":round(di,4),
      "v1_plus_sacks":v1+0.15*ds,
      "v1_plus_ints":v1+0.30*di,
      "v1_plus_both":v1+0.15*ds+0.30*di})
  for team,c in weekly[week]:history[team].update(c)
 all_results[season]=audit
def metrics(rows):
 out={}
 for k in ("v1","v1_plus_sacks","v1_plus_ints","v1_plus_both"):
  errors=[r[k]-r["actual"] for r in rows]
  out[k]={"mae":round(mean([abs(e) for e in errors]),4),
          "rmse":round(math.sqrt(mean([e*e for e in errors])),4),
          "bias":round(mean(errors),4)}
 return out
combined=[r for season in sorted(all_results) for r in all_results[season]]
dest=ROOT/"dst_2024_2025_incremental_opponent_risk_challenger.csv"
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(combined[0]));writer.writeheader();writer.writerows(combined)
print(json.dumps({"status":"REVIEW_ONLY","samples_by_season":{str(k):len(v) for k,v in all_results.items()},
 "by_season":{str(k):metrics(v) for k,v in all_results.items()},
 "combined":metrics(combined),"saved":str(dest),
 "limitations":["Uses existing frozen V1 historical predictions and reconstructed ESPN-stat-based targets",
 "Candidate coefficients 0.15 and 0.30 are exploratory, NOT validated or tuned",
 "Multiple candidates tested on same two seasons; improvement is not proof of out-of-sample generalization",
 "QB injuries and offensive line injury status are not included"],
 "production_changed":False},indent=2))
