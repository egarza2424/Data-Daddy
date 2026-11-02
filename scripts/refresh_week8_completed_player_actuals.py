#!/usr/bin/env python3
"""Refresh completed Week 8 player actual PPR from nflverse weekly stats.
Never changes projections, rankings, or unfinished Monday CHI/SEA scores.
Run in Codespaces; review console summary before committing JSON.
"""
import collections,json,pathlib,urllib.request
YEAR,WEEK=2026,8
path=pathlib.Path("data/actual-ppr-2026.json")
if not path.exists():raise SystemExit("Missing "+str(path))
payload=json.loads(path.read_text())
existing=payload.get("players",[])
if not isinstance(existing,list):raise SystemExit("Unexpected feed structure")
url="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=8"
with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=45) as response:board=json.load(response)
aliases={"LAR":"LA","WSH":"WAS","JAC":"JAX"}
finished=set()
for event in board.get("events",[]):
 if not event.get("status",{}).get("type",{}).get("completed"):continue
 comps=(event.get("competitions") or [{}])[0].get("competitors",[])
 if len(comps)!=2:continue
 teams=[aliases.get(c.get("team",{}).get("abbreviation"),c.get("team",{}).get("abbreviation")) for c in comps]
 if set(teams)=={"CHI","SEA"}:continue
 finished.update(teams)
if len(finished)<20:raise SystemExit("Too few final-game teams: "+str(len(finished)))
try:
 import duckdb
 db=duckdb.connect()
 source="https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.parquet"
 cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[source]).fetchall()}
 required={"season","week","player_display_name","team","position","fantasy_points_ppr"}
 if not required.issubset(cols):raise RuntimeError("Missing columns: "+str(required-cols))
 records=db.execute("SELECT season,week,player_display_name,team,position,fantasy_points_ppr FROM read_parquet(?) WHERE season=? AND week=?",[source,YEAR,WEEK]).fetchall()
except Exception as e:raise SystemExit("Unable to retrieve nflverse completed player stats: "+str(e))
def key(row):
 return (int(row["season"]),int(row["week"]),str(row["player_display_name"]).strip().casefold(),str(row["team"]).upper(),str(row["position"]).upper())
index={key(row):i for i,row in enumerate(existing) if all(k in row for k in ("season","week","player_display_name","team","position"))}
added=updated=0
for season,week,name,team,pos,points in records:
 team=aliases.get(team,team)
 if team not in finished or pos not in ("QB","RB","WR","TE") or points is None or not name:continue
 item={"season":YEAR,"week":WEEK,"player_display_name":str(name),"team":team,"position":pos,"fantasy_points_ppr":round(float(points),2)}
 k=key(item)
 if k in index:
  old=existing[index[k]]
  if old.get("fantasy_points_ppr")!=item["fantasy_points_ppr"]:
   # Do not silently overwrite already published numbers.
   raise SystemExit("Conflicting existing score for "+str(k)+": "+str(old.get("fantasy_points_ppr"))+" vs "+str(item["fantasy_points_ppr"]))
 else:
  index[k]=len(existing);existing.append(item);added+=1
if added<100:raise SystemExit("Expected many Sunday player scores, found only "+str(added)+"; file unchanged")
payload["players"]=existing
path.write_text(json.dumps(payload,separators=(",",":"))+"\n")
counts=collections.Counter(row.get("week") for row in existing)
print(json.dumps({"status":"GREEN","final_teams":sorted(finished),"week8_rows":counts[WEEK],"new_rows":added,"saved":str(path),"notes":["No Monday CHI/SEA scores","No projections or model changes","Review and commit updated data file to publish"]},indent=2))
