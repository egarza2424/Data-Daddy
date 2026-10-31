#!/usr/bin/env python3
"""Export reconstructed 2025 ESPN-stat-based D/ST scores to validation CSV only."""
import csv,json,urllib.request,pathlib,collections
src=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not src.exists():raise SystemExit("Run python scripts/export_dst_2025_provisional_csv.py first")
with src.open(newline="") as f:rows=list(csv.DictReader(f))
teams=dict(zip("Cardinals Falcons Ravens Bills Panthers Bears Bengals Browns Cowboys Broncos Lions Packers Texans Colts Jaguars Chiefs Raiders Chargers Rams Dolphins Vikings Patriots Saints Giants Jets Eagles Steelers 49ers Seahawks Buccaneers Titans Commanders".split(),"ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split()))
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as f:players=json.load(f)
lookup={}
for p in players:
 if p.get("defaultPositionId")!=16:continue
 abbr=teams.get((p.get("fullName") or "").replace(" D/ST",""))
 for s in p.get("stats",[]):
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
dest=pathlib.Path("projection-model/validation/dst_2025_espn_stat_based_scores.csv")
fields=["week","game_id","defense","reconstructed_dst_points","provisional_dst_points","difference","espn_sacks","espn_interceptions","espn_fumble_recoveries","espn_blocked_kicks","espn_total_dst_td","espn_safeties","espn_defensive_two_point_conversions","espn_points_allowed","source_status"]
out=[]
for r in rows:
 key=(int(r["week"]),r["defense"])
 if key not in lookup:raise SystemExit("Missing ESPN record: "+str(key))
 s=lookup[key];v=lambda k:float(s.get(str(k),0))
 score=v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+tier(v(120))
 out.append({"week":key[0],"game_id":r["game_id"],"defense":key[1],"reconstructed_dst_points":score,"provisional_dst_points":r["provisional_dst_points"],"difference":score-float(r["provisional_dst_points"]),"espn_sacks":v(99),"espn_interceptions":v(95),"espn_fumble_recoveries":v(96),"espn_blocked_kicks":v(97),"espn_total_dst_td":v(105),"espn_safeties":v(98),"espn_defensive_two_point_conversions":v(205),"espn_points_allowed":v(120),"source_status":"RECONSTRUCTED_NOT_OFFICIAL_ESPN_POINTS"})
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
print(json.dumps({"saved":str(dest),"rows":len(out),"changed_from_provisional":sum(x["difference"]!=0 for x in out),"status":"RECONSTRUCTED NOT OFFICIAL ESPN FANTASY POINTS","production_changed":False},indent=2))
