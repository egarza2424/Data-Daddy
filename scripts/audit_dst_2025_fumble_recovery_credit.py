#!/usr/bin/env python3
"""Read-only audit: fumbles lost vs confirmed defensive recoveries, 2025."""
import duckdb,json,collections,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
fields=["game_id","week","play_id","posteam","defteam","fumble_lost","fumble_recovery_1_team","fumble_recovery_2_team","desc"]
select=", ".join('"'+c+'"' if c in cols else 'NULL AS "'+c+'"' for c in fields)
rows=db.execute(f"""SELECT {select} FROM read_parquet(?)
WHERE season=2025 AND week BETWEEN 1 AND 18 AND fumble_lost=1
AND game_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'""",[src]).fetchall()
groups=collections.Counter(); examples=[]
for game,week,pid,off,defteam,lost,r1,r2,description in rows:
 recovery={r for r in (r1,r2) if r}
 if defteam in recovery:category="confirmed_defensive_recovery"
 elif recovery:category="recovery_other_team"
 else:category="recovery_team_missing"
 groups[category]+=1
 if category!="confirmed_defensive_recovery" and len(examples)<25:
  examples.append({"game_id":game,"week":week,"play_id":pid,"posteam":off,"defteam":defteam,"recovery_teams":sorted(recovery),"description":(description or "")[:180]})
print(json.dumps({"candidate_fumbles_lost":len(rows),"classification":dict(groups),
"exceptions_sample":examples,
"caution":"Recovery flags and ESPN D/ST credit require external validation; no fantasy scoring performed.",
"changes":"Read-only; no live site, rankings, projections, or model weights changed."},indent=2))
