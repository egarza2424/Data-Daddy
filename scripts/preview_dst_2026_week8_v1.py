#!/usr/bin/env python3
"""Read-only DATA DADDY Week 8 2026 D/ST V1 preview, fixed historical weights."""
import collections,csv,json,pathlib,urllib.request
season=2026;week_target=8
# Verified 2026 Week 8 slate. Home team is second. Thu game already played; exclude.
games=[("BAL","BUF"),("TEN","CIN"),("ARI","DAL"),("MIN","DET"),("IND","JAX"),("LV","NYJ"),("CLE","PIT"),("ATL","TB"),("LAC","LA"),("KC","DEN"),("NE","MIA"),("PHI","WAS"),("CHI","SEA")]
teams=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
url=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as f:players=json.load(f)
def tier(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
hist=collections.defaultdict(list)
for p in players:
 if p.get("defaultPositionId")!=16:continue
 team=teams.get((p.get("fullName") or "").replace(" D/ST",""))
 if not team:continue
 for s in p.get("stats",[]):
  w=s.get("scoringPeriodId")
  if s.get("seasonId")!=season or s.get("statSourceId")!=0 or s.get("statSplitTypeId")!=1 or not isinstance(w,int) or not 1<=w<week_target:continue
  st=s.get("stats") or {};v=lambda k:float(st.get(str(k),0))
  # ESPN sometimes provides zeroed records for bye weeks. Require at least one actual stat.
  if not st or not any(v(k) for k in (99,95,96,97,105,120,127)):continue
  score=v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+tier(v(120))
  hist[team].append({"week":w,"actual":score,"sacks":v(99),"takeaways":v(95)+v(96),"points_allowed":v(120)})
for team in hist:hist[team].sort(key=lambda r:r["week"])
# Map opponent vulnerability using verified 2026 Weeks 1-7 game IDs from nflverse schedule.
try:
 import duckdb
 db=duckdb.connect()
 sched=db.execute("SELECT DISTINCT week,home_team,away_team FROM read_parquet(?) WHERE season=2026 AND week BETWEEN 1 AND 7 AND game_id IS NOT NULL",["https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet"]).fetchall()
except Exception as e:raise SystemExit("2026 opponent schedule unavailable: "+str(e))
offhist=collections.defaultdict(list)
for w,home,away in sched:
 for defense,opponent in ((home,away),(away,home)):
  matching=[r for r in hist[defense] if r["week"]==w]
  if len(matching)==1:offhist[opponent].append(matching[0])
for team in offhist:offhist[team].sort(key=lambda r:r["week"])
prior=[r for rs in hist.values() for r in rs]
if len(prior)<150:raise SystemExit("Too few completed ESPN defense-games for a reliable preview: "+str(len(prior)))
def avg(xs):return sum(xs)/len(xs) if xs else 0.
base=avg([r["actual"] for r in prior]);ls=avg([r["sacks"] for r in prior]);lt=avg([r["takeaways"] for r in prior]);lp=avg([r["points_allowed"] for r in prior])
out=[]
for away,home in games:
 for defense,opponent,is_home in ((away,home,False),(home,away,True)):
  dh=hist[defense];oh=offhist[opponent]
  if len(dh)<3 or len(oh)<3:raise SystemExit(f"Insufficient history for {defense} vs {opponent}: defense={len(dh)}, opponent={len(oh)}")
  ds=(sum(r["sacks"] for r in dh)+5*ls)/(len(dh)+5)
  dt=(sum(r["takeaways"] for r in dh)+8*lt)/(len(dh)+8)
  dpa=(sum(r["points_allowed"] for r in dh)+8*lp)/(len(dh)+8)
  ov=(sum(r["actual"] for r in oh)+8*base)/(len(oh)+8)
  projection=base+0.8*(ds-ls)+0.8*(dt-lt)+0.5*(ov-base)-0.05*(dpa-lp)
  out.append({"rank":0,"defense":defense,"opponent":opponent,"home":is_home,"projected_dst_points":round(projection,2),"opponent_vulnerability_signal":round(ov-base,2),"sack_signal":round(ds-ls,2),"takeaway_signal":round(dt-lt,2),"points_allowed_signal":round(dpa-lp,2),"defense_games":len(dh),"opponent_games":len(oh),"status":"REVIEW_ONLY"})
out.sort(key=lambda r:(-r["projected_dst_points"],r["defense"]))
for i,r in enumerate(out,1):r["rank"]=i
dest=pathlib.Path("projection-model/validation/dst_2026_week8_v1_review_only.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
print(json.dumps({"week":8,"ranked_defenses":len(out),"historical_games":len(prior),"baseline":round(base,3),"top_15":out[:15],"saved":str(dest),"notes":["Review only: fixed 2024/2025 weights, no deployment","Thursday Carolina-Green Bay already played; excluded","Bye: HOU NO NYG SF","No home-field adjustment in validated V1","ESPN stat-derived reconstructed historical points, not official ESPN fantasy totals"],"production_changed":False},indent=2))
