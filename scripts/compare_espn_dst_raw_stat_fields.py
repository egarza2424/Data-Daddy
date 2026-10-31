#!/usr/bin/env python3
"""Read-only ESPN-to-nflverse D/ST stat field correlation; no guessed labels or scoring changes."""
import csv,json,urllib.request,collections,statistics,pathlib
path=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
if not path.exists():raise SystemExit("Missing provisional CSV. First run: python scripts/export_dst_2025_provisional_csv.py")
with path.open(newline="") as f: local=list(csv.DictReader(f))
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as r:players=json.load(r)
name_to_abbr={"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC","Rams":"LA","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB","Titans":"TEN","Commanders":"WAS"}
lookup={}
for p in players:
 if p.get("defaultPositionId")!=16:continue
 name=(p.get("fullName") or "").replace(" D/ST","")
 abbr=name_to_abbr.get(name)
 if not abbr:print("UNMAPPED_ESPN_TEAM",repr(name));continue
 for s in p.get("stats",[]):
  if s.get("seasonId")==2025 and s.get("statSourceId")==0 and s.get("statSplitTypeId")==1 and 1<=s.get("scoringPeriodId",0)<=18:
   lookup[(s["scoringPeriodId"],abbr)]=s.get("stats") or {}
pairs=[(row,lookup[(int(row["week"]),row["defense"])]) for row in local if (int(row["week"]),row["defense"]) in lookup]
fields=["sacks","interceptions","confirmed_defensive_fumble_recoveries","blocked_kick_candidates","defensive_td","special_teams_td","safeties","defensive_two_point_conversions","provisional_points_allowed"]
ids=sorted({k for _,s in pairs for k in s},key=int)
results={}
for field in fields:
 target=[float(row[field] or 0) for row,_ in pairs]
 candidates=[]
 for key in ids:
  xs=[float(s.get(key,0)) for _,s in pairs]
  if len(set(xs))<2:continue
  exact=sum(a==b for a,b in zip(xs,target))
  try:corr=statistics.correlation(xs,target) if len(set(target))>1 else None
  except (ValueError,statistics.StatisticsError):corr=None
  candidates.append({"espn_id":key,"exact_rows":exact,"correlation":round(corr,4) if corr is not None else None})
 results[field]=sorted(candidates,key=lambda c:(c["exact_rows"],c["correlation"] if c["correlation"] is not None else -2),reverse=True)[:8]
print(json.dumps({"espn_weekly_rows":len(lookup),"provisional_rows":len(local),"matched_rows":len(pairs),"unmatched_provisional":[{"week":r["week"],"defense":r["defense"]} for r in local if (int(r["week"]),r["defense"]) not in lookup][:20],"candidate_field_matches":results,"warning":"Correlation is exploratory, not authoritative field mapping. No scores are calculated or changed."},indent=2))
