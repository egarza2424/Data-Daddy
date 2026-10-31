#!/usr/bin/env python3
"""Read-only revised ESPN D/ST component scoring comparison. No production writes."""
import csv,json,urllib.request,collections,pathlib
path=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not path.exists():raise SystemExit("Run python scripts/export_dst_2025_provisional_csv.py first")
with path.open(newline="") as f: rows=list(csv.DictReader(f))
teams=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
hdr={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=hdr),timeout=35) as f:players=json.load(f)
lookup={}
for player in players:
 if player.get("defaultPositionId")!=16:continue
 abbr=teams.get((player.get("fullName") or "").replace(" D/ST",""))
 for s in player.get("stats",[]):
  if abbr and s.get("seasonId")==2025 and s.get("statSourceId")==0 and s.get("statSplitTypeId")==1 and 1<=s.get("scoringPeriodId",0)<=18:lookup[(s["scoringPeriodId"],abbr)]=s.get("stats") or {}
def pa_score(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
changes=[];matched=0
for row in rows:
 key=(int(row["week"]),row["defense"])
 if key not in lookup:continue
 matched+=1;s=lookup[key];v=lambda k:float(s.get(str(k),0))
 old=float(row["provisional_dst_points"])
 # Use ESPN field 105 for total D/ST touchdowns: do NOT add defensive and special-teams separately.
 estimate=v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+pa_score(v(120))
 if estimate!=old:
  changes.append({"week":key[0],"defense":key[1],"game_id":row["game_id"],"provisional":old,"espn_stat_based_estimate":estimate,"difference":estimate-old,"espn_total_td":v(105),"provisional_total_td":float(row["defensive_td"])+float(row["special_teams_td"]),"points_allowed_tier_difference":pa_score(v(120))-pa_score(float(row["provisional_points_allowed"]))})
print(json.dumps({"matched_games":matched,"changed_games":len(changes),"unchanged_games":matched-len(changes),"difference_distribution":dict(sorted(collections.Counter(str(r["difference"]) for r in changes).items())),"changes":changes,"cautions":["Estimated from ESPN raw stats using empirically inferred field IDs, not ESPN's official fantasy points.","No double-counting of TD: uses field 105 only.","ESPN appliedTotal unavailable; official scoring rules and field mappings still require verification.","No files, live site, rankings, projections, or model weights changed."]},indent=2))
