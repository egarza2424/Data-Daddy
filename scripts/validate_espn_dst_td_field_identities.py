#!/usr/bin/env python3
"""Read-only: test candidate ESPN D/ST TD identities against 2025 provisional team-games."""
import csv,json,urllib.request,collections,pathlib
p=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not p.exists():raise SystemExit("Run python scripts/export_dst_2025_provisional_csv.py first")
with p.open(newline="") as f:rows=list(csv.DictReader(f))
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
checks=collections.Counter();discrepancies=[]
for r in rows:
 key=(int(r["week"]),r["defense"])
 if key not in lookup:continue
 s=lookup[key]
 v=lambda k:float(s.get(str(k),0))
 old_def=float(r["defensive_td"]);old_st=float(r["special_teams_td"])
 identities={"105_equals_101_102_103_104":v(105)==sum(v(i) for i in (101,102,103,104)),"105_equals_94_101_102":v(105)==sum(v(i) for i in (94,101,102)),"94_equals_103_104":v(94)==v(103)+v(104),"provisional_total_equals_105":old_def+old_st==v(105),"provisional_def_equals_94":old_def==v(94),"provisional_st_equals_101_102":old_st==v(101)+v(102)}
 for label,match in identities.items():checks[label+"_matched" if match else label+"_mismatched"]+=1
 if not identities["provisional_total_equals_105"] or not identities["provisional_st_equals_101_102"]:
  discrepancies.append({"week":key[0],"defense":key[1],"provisional_def":old_def,"provisional_st":old_st,"espn_94":v(94),"espn_101":v(101),"espn_102":v(102),"espn_103":v(103),"espn_104":v(104),"espn_105":v(105)})
print(json.dumps({"matched":len(rows),"identity_tests":dict(checks),"discrepancy_examples":discrepancies[:35],"note":"Field identities are empirical; not authoritative scoring labels. No fantasy totals calculated or production modified."},indent=2))
