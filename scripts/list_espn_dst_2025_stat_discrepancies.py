#!/usr/bin/env python3
"""Read-only: show exact ESPN vs provisional D/ST stat discrepancies by team/week."""
import csv,json,urllib.request,collections,pathlib
path=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not path.exists():raise SystemExit("Missing provisional CSV; run python scripts/export_dst_2025_provisional_csv.py")
with path.open(newline="") as f:local=list(csv.DictReader(f))
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as r:players=json.load(r)
teams={"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC","Rams":"LA","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB","Titans":"TEN","Commanders":"WAS"}
lookup={}
for p in players:
 if p.get("defaultPositionId")!=16:continue
 abbr=teams.get((p.get("fullName") or "").replace(" D/ST",""))
 if not abbr:continue
 for s in p.get("stats",[]):
  if s.get("seasonId")==2025 and s.get("statSourceId")==0 and s.get("statSplitTypeId")==1 and 1<=s.get("scoringPeriodId",0)<=18:lookup[(s["scoringPeriodId"],abbr)]=s.get("stats") or {}
mapping={"sacks":"99","interceptions":"95","confirmed_defensive_fumble_recoveries":"96","blocked_kick_candidates":"97","defensive_td":"94","safeties":"98","defensive_two_point_conversions":"205","provisional_points_allowed":"120"}
out={}
for field,stat_id in mapping.items():
 differences=[]
 for row in local:
  key=(int(row["week"]),row["defense"])
  if key not in lookup:continue
  observed=float(lookup[key].get(stat_id,0));provisional=float(row[field] or 0)
  if observed!=provisional:differences.append({"week":key[0],"defense":key[1],"espn":observed,"provisional":provisional,"delta":observed-provisional,"game_id":row["game_id"]})
 out[field]={"mismatch_count":len(differences),"mismatches":differences[:40]}
print(json.dumps({"matched_games":sum((int(r["week"]),r["defense"]) in lookup for r in local),"field_mismatches":out,"warning":"Stat IDs are inferred from 544-game agreement, not official ESPN documentation. Read-only; no scoring changes."},indent=2))
