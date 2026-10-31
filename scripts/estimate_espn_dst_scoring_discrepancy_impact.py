#!/usr/bin/env python3
"""Read-only: quantify scoring impact of ESPN-vs-provisional D/ST component differences.
ESPN IDs inferred empirically, not an official mapping. No production writes.
"""
import csv,json,urllib.request,collections,pathlib
p=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not p.exists():raise SystemExit("Missing CSV; run python scripts/export_dst_2025_provisional_csv.py")
with p.open(newline="") as f: rows=list(csv.DictReader(f))
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
def tier(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
changes=[]
for row in rows:
 key=(int(row["week"]),row["defense"])
 if key not in lookup:continue
 s=lookup[key]
 def v(k):return float(s.get(k,0))
 old=float(row["provisional_dst_points"])
 pa=v("120")
 # ESPN inferred IDs: 99 sacks,95 INT,96 FR,97 blocks,94 defensive TD,98 safety,205 2pt
 # Special teams TD ESPN ID is NOT verified: retain provisional value and explicitly flag.
 estimated=v("99")+2*v("95")+2*v("96")+2*v("97")+6*v("94")+6*float(row["special_teams_td"])+2*v("98")+2*v("205")+tier(pa)
 delta=estimated-old
 if delta:changes.append({"week":key[0],"defense":key[1],"game_id":row["game_id"],"provisional":old,"espn_component_estimate":estimated,"delta":delta,"pa_old":int(float(row["provisional_points_allowed"])),"pa_espn":pa,"pa_tier_delta":tier(pa)-tier(int(float(row["provisional_points_allowed"]))),"special_teams_td_unverified":float(row["special_teams_td"])})
print(json.dumps({"matched":len(rows),"changed_estimates":len(changes),"delta_distribution":dict(sorted(collections.Counter(str(x["delta"]) for x in changes).items())),"largest_differences":sorted(changes,key=lambda x:abs(x["delta"]),reverse=True)[:35],"limitations":["Not verified ESPN fantasy point totals: ESPN appliedTotal is null.","Special teams TD field is not mapped; retained provisional counts.","ESPN stat IDs inferred from matches, not authoritative metadata.","No production changes."]},indent=2))
