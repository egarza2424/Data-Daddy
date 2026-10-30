#!/usr/bin/env python3
"""Read-only 2025 blocked-kick D/ST candidates by team-game and play type."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
fields=["game_id","week","play_id","posteam","defteam","play_type","desc","field_goal_result","extra_point_result","punt_blocked"]
sel=", ".join('"'+f+'"' if f in cols else 'NULL AS "'+f+'"' for f in fields)
rows=db.execute(f"""SELECT {sel} FROM read_parquet(?) WHERE season=2025
AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
AND play_type IN ('punt','field_goal','extra_point')""",[src]).fetchall()
events=[]
for game,week,pid,off,defteam,typ,desc,fg,xp,punt in rows:
 d=(desc or "").upper()
 flags=(str(fg or "")+" "+str(xp or "")).lower()
 if "BLOCKED" not in d and "blocked" not in flags and punt!=1:continue
 events.append({"game_id":game,"week":week,"play_id":pid,"defense":defteam,
 "play_type":typ,"description":(desc or "")[:180]})
counts=collections.Counter(e["play_type"] for e in events)
print(json.dumps({"blocked_kick_candidates":len(events),"by_play_type":dict(counts),
"sample_events":events[:15],
"cautions":["Candidate detection from descriptions/flags; ESPN eligibility and credited team require validation.","Extra-point blocks may be treated differently from blocked punts/field goals.","No live site, scoring, rankings, projections, or model weights changed."]},indent=2))
