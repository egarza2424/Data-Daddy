#!/usr/bin/env python3
"""Read-only Week 9 D/ST targeted review: ESPN stat-component TD audit."""
import collections,csv,json,pathlib,urllib.request
src=pathlib.Path("projection-model/validation/dst_2026_week9_underlying_stats_review.csv")
if not src.exists():raise SystemExit("Run python scripts/audit_dst_2026_week9_underlying_stats.py first")
with src.open(newline="") as f:rows=list(csv.DictReader(f))
teams={"TB","MIN","NO","HOU","DEN","JAX"}
selected={r["defense"]:r for r in rows if r["defense"] in teams}
if len(selected)!=6:raise SystemExit("Missing target teams in underlying stats CSV")
names=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/players?view=kona_player_info"
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as f:players=json.load(f)
stats=collections.defaultdict(dict)
for p in players:
 if p.get("defaultPositionId")!=16:continue
 team=names.get((p.get("fullName") or "").replace(" D/ST",""))
 if team not in teams:continue
 for s in p.get("stats",[]):
  w=s.get("scoringPeriodId")
  if s.get("seasonId")!=2026 or s.get("statSourceId")!=0 or s.get("statSplitTypeId")!=1 or not isinstance(w,int) or not 1<=w<=8:continue
  st=s.get("stats") or {}
  if not st:continue
  v=lambda k:float(st.get(str(k),0))
  if not any(v(k) for k in (99,95,96,97,105,120,127)):continue
  stats[team][w]={"sacks":v(99),"interceptions":v(95),"fumble_recoveries":v(96),"return_tds_stat_105":v(105),"blocked_kicks_stat_98":v(98),"points_allowed":v(120),"espn_reported_fantasy_points":s.get("appliedTotal")}
out=[]
for team in ("TB","MIN","NO","HOU","DEN","JAX"):
 r=selected[team];weeks=sorted(stats[team]);recent=weeks[-3:]
 if len(recent)!=3:raise SystemExit(f"Insufficient completed ESPN weeks for {team}")
 for w in weeks:
  s=stats[team][w]
  out.append({"defense":team,"week":w,"is_last_three":w in recent,"opponent_week9":r["opponent"],"model_rank":r["rank"],"model_projection":r["projected_dst_points"],**s,"note":"ESPN raw stat 105 is not independently validated as all DST TD mechanisms"})
dest=pathlib.Path("projection-model/validation/dst_2026_week9_targeted_td_audit.csv")
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
summary=[]
for team in ("TB","MIN","NO","HOU","DEN","JAX"):
 weeks=sorted(stats[team]);recent=weeks[-3:]
 summary.append({"defense":team,"opponent":selected[team]["opponent"],"rank":selected[team]["rank"],"projection":selected[team]["projected_dst_points"],"last_three_weeks":recent,"last_three_stat105_tds":sum(stats[team][w]["return_tds_stat_105"] for w in recent),"season_stat105_tds":sum(stats[team][w]["return_tds_stat_105"] for w in weeks),"last_three_sacks":sum(stats[team][w]["sacks"] for w in recent),"last_three_interceptions":sum(stats[team][w]["interceptions"] for w in recent),"last_three_fumble_recoveries":sum(stats[team][w]["fumble_recoveries"] for w in recent),"reconstructed_recent_ppg":selected[team]["dst_reconstructed_points_last3"]})
print(json.dumps({"week":9,"status":"REVIEW_ONLY","summary":summary,"saved":str(dest),"caveats":["Stat 105 TD coverage must be verified against play-by-play before treating as all D/ST touchdowns","ESPN reported fantasy totals may be missing; do not substitute reconstructed totals as official","No projections, editorial ranks, model weights, or live website changes"]},indent=2))
