#!/usr/bin/env python3
"""Read-only Week 9 D/ST underlying-stat audit. Does not change projections."""
import collections,csv,json,pathlib,urllib.request
import duckdb
ROOT=pathlib.Path("projection-model/validation")
SOURCE=ROOT/"dst_2026_week9_v1_review_only.csv"
if not SOURCE.exists():raise SystemExit("Run python scripts/preview_dst_2026_week9_v1.py first")
with SOURCE.open(newline="") as f:projections=list(csv.DictReader(f))
if len(projections)!=30:raise SystemExit(f"Expected 30 Week 9 projections, found {len(projections)}")
url="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet"
db=duckdb.connect()
rows=db.execute("""SELECT week,game_id,play_id,posteam,defteam,
COALESCE(sack,0),COALESCE(interception,0),COALESCE(fumble_lost,0),
COALESCE(qb_dropback,0),COALESCE(pass_attempt,0)
FROM read_parquet(?) WHERE season=2026 AND week BETWEEN 1 AND 8
AND game_id IS NOT NULL AND play_id IS NOT NULL AND posteam IS NOT NULL
AND defteam IS NOT NULL""",[url]).fetchall()
off=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.Counter()))
defense=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.Counter()))
seen=set()
for w,g,p,attack,guard,sack,inter,fumble,drop,attempt in rows:
 key=(g,p)
 if key in seen:continue
 seen.add(key)
 a=off[attack][w];d=defense[guard][w]
 a["plays"]+=1;d["plays"]+=1
 if drop==1 or attempt==1 or sack==1:a["dropbacks"]+=1
 if sack==1:a["sacks_allowed"]+=1;d["sacks"]+=1
 if inter==1:a["interceptions_thrown"]+=1;d["interceptions"]+=1
 if fumble==1:a["fumbles_lost_candidate"]+=1;d["opponent_fumbles_lost_candidate"]+=1
# Fetch ESPN D/ST box scores for actual fantasy points and points allowed.
names=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/players?view=kona_player_info",headers=headers),timeout=45) as f:players=json.load(f)
espn=collections.defaultdict(dict)
def pa_tier(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
for p in players:
 if p.get("defaultPositionId")!=16:continue
 team=names.get((p.get("fullName") or "").replace(" D/ST",""))
 if not team:continue
 for s in p.get("stats",[]):
  w=s.get("scoringPeriodId")
  if s.get("seasonId")!=2026 or s.get("statSourceId")!=0 or s.get("statSplitTypeId")!=1 or not isinstance(w,int) or not 1<=w<=8:continue
  st=s.get("stats") or {}
  if not st:continue
  v=lambda k:float(st.get(str(k),0))
  if not any(v(k) for k in (99,95,96,97,105,120,127)):continue
  espn[team][w]={"reconstructed_ppr":v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+pa_tier(v(120)),"points_allowed":v(120)}
def mean(vals):return round(sum(vals)/len(vals),2) if vals else None
out=[]
for p in projections:
 team=p["defense"];opp=p["opponent"]
 d=defense[team];o=off[opp];e=espn[team]
 dw=sorted(d);ow=sorted(o);ew=sorted(e)
 n=sum(d[w]["dropbacks"] for w in dw)
 on=sum(o[w]["dropbacks"] for w in ow)
 out.append({"rank":p["rank"],"defense":team,"opponent":opp,"projected_dst_points":p["projected_dst_points"],
 "defense_games_pbp":len(dw),"def_sacks_per_game":mean([d[w]["sacks"] for w in dw]),
 "def_sacks_last3":mean([d[w]["sacks"] for w in dw[-3:]]),
 "def_interceptions_per_game":mean([d[w]["interceptions"] for w in dw]),
 "def_opponent_fumbles_lost_candidate_per_game":mean([d[w]["opponent_fumbles_lost_candidate"] for w in dw]),
 "def_takeaways_candidate_per_game":mean([d[w]["interceptions"]+d[w]["opponent_fumbles_lost_candidate"] for w in dw]),
 "dst_reconstructed_points_per_game":mean([e[w]["reconstructed_ppr"] for w in ew]),
 "dst_reconstructed_points_last3":mean([e[w]["reconstructed_ppr"] for w in ew[-3:]]),
 "points_allowed_per_game":mean([e[w]["points_allowed"] for w in ew]),
 "points_allowed_last3":mean([e[w]["points_allowed"] for w in ew[-3:]]),
 "opponent_games_pbp":len(ow),"opponent_sacks_allowed_per_game":mean([o[w]["sacks_allowed"] for w in ow]),
 "opponent_sacks_allowed_last3":mean([o[w]["sacks_allowed"] for w in ow[-3:]]),
 "opponent_sack_rate_pct":round(100*sum(o[w]["sacks_allowed"] for w in ow)/on,2) if on else None,
 "opponent_interceptions_thrown_per_game":mean([o[w]["interceptions_thrown"] for w in ow]),
 "opponent_fumbles_lost_candidate_per_game":mean([o[w]["fumbles_lost_candidate"] for w in ow]),
 "opponent_turnovers_candidate_per_game":mean([o[w]["interceptions_thrown"]+o[w]["fumbles_lost_candidate"] for w in ow]),
 "qb_status":"NOT_VERIFIED","offensive_line_status":"NOT_VERIFIED","status":"REVIEW_ONLY"})
if any(r["defense_games_pbp"]<5 or r["opponent_games_pbp"]<5 for r in out):raise SystemExit("Insufficient pbp coverage for one or more teams; no output written")
dest=ROOT/"dst_2026_week9_underlying_stats_review.csv"
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
print(json.dumps({"week":9,"defenses":len(out),"saved":str(dest),"top_15":out[:15],"notes":["No rankings or projections modified","Reconstructed ESPN scores, not official ESPN fantasy totals","Fumbles-lost fields are candidate indicators; verify defensive credit","Injuries not verified","Last 3 means last 3 played games, not calendar weeks"]},indent=2))
