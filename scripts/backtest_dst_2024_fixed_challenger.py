#!/usr/bin/env python3
"""Read-only 2024 out-of-season D/ST validation of FIXED 2025 challenger weights."""
import collections,csv,json,math,pathlib,urllib.request
import duckdb
season=2024
url=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as f:players=json.load(f)
teams=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
schedule_url="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2024.parquet"
db=duckdb.connect()
try:
 games=db.execute("SELECT DISTINCT week,game_id,home_team,away_team FROM read_parquet(?) WHERE season=2024 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL",[schedule_url]).fetchall()
except Exception as e:raise SystemExit("Could not fetch nflverse 2024 game schedule: "+str(e))
schedule={(int(w),team):(gid,home if team==away else away) for w,gid,home,away in games for team in (home,away)}
def tier(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
rows=[];seen=set()
for p in players:
 if p.get("defaultPositionId")!=16:continue
 team=teams.get((p.get("fullName") or "").replace(" D/ST",""))
 if not team:continue
 for s in p.get("stats",[]):
  w=s.get("scoringPeriodId")
  if s.get("seasonId")!=season or s.get("statSourceId")!=0 or s.get("statSplitTypeId")!=1 or not isinstance(w,int) or not 1<=w<=18 or (w,team) not in schedule:continue
  st=s.get("stats") or {};v=lambda k:float(st.get(str(k),0))
  score=v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+tier(v(120))
  gid,opponent=schedule[(w,team)]
  if (w,team) in seen:raise SystemExit("Duplicate defense-week "+str((w,team)))
  seen.add((w,team))
  rows.append({"week":w,"game_id":gid,"defense":team,"opponent":opponent,"actual":score,"sacks":v(99),"takeaways":v(95)+v(96),"points_allowed":v(120)})
if len(rows)!=544:raise SystemExit(f"Expected 544 2024 team-games, got {len(rows)}. No results saved.")
by_week=collections.defaultdict(list)
for r in rows:by_week[r["week"]].append(r)
hist=collections.defaultdict(list);offhist=collections.defaultdict(list);pred=[]
def avg(xs):return sum(xs)/len(xs) if xs else 0.
for week in sorted(by_week):
 prior=[r for teamrows in hist.values() for r in teamrows]
 if prior:
  baseline=avg([r["actual"] for r in prior]);ls=avg([r["sacks"] for r in prior]);lt=avg([r["takeaways"] for r in prior]);lp=avg([r["points_allowed"] for r in prior])
 for r in by_week[week]:
  dh=hist[r["defense"]];oh=offhist[r["opponent"]]
  if week<5 or len(dh)<3 or len(oh)<3:continue
  ds=(sum(x["sacks"] for x in dh)+5*ls)/(len(dh)+5)
  dt=(sum(x["takeaways"] for x in dh)+8*lt)/(len(dh)+8)
  dpa=(sum(x["points_allowed"] for x in dh)+8*lp)/(len(dh)+8)
  ov=(sum(x["actual"] for x in oh)+8*baseline)/(len(oh)+8)
  variants={"global":baseline,"sacks":baseline+0.8*(ds-ls),"sacks_takeaways":baseline+0.8*(ds-ls)+0.8*(dt-lt),"opponent":baseline+0.5*(ov-baseline),"all":baseline+0.8*(ds-ls)+0.8*(dt-lt)+0.5*(ov-baseline)-0.05*(dpa-lp)}
  pred.append({"week":week,"defense":r["defense"],"opponent":r["opponent"],"actual":r["actual"],**variants})
 for r in by_week[week]:hist[r["defense"]].append(r);offhist[r["opponent"]].append(r)
metrics={}
for key in ("global","sacks","sacks_takeaways","opponent","all"):
 errs=[x[key]-x["actual"] for x in pred]
 metrics[key]={"mae":round(avg([abs(e) for e in errs]),4),"rmse":round(math.sqrt(avg([e*e for e in errs])),4)}
dest=pathlib.Path("projection-model/validation/dst_2024_fixed_2025_challenger_predictions.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=["week","defense","opponent","actual","global","sacks","sacks_takeaways","opponent","all"]);writer.writeheader();writer.writerows(pred)
print(json.dumps({"season":2024,"historical_team_games":len(rows),"evaluated":len(pred),"weeks":"5-18","metrics":metrics,"best_mae":min(metrics,key=lambda x:metrics[x]["mae"]),"saved":str(dest),"cautions":["Same fixed coefficients as 2025; no weight fitting","ESPN stat-based reconstructed scores, not independently confirmed official ESPN fantasy totals","2024 evaluation is a distinct season, but not a fully independent pre-registration","No production changes"]},indent=2))
