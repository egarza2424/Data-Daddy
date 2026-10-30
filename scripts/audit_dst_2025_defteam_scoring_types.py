#!/usr/bin/env python3
"""Read-only diagnostic of scores credited to defteam in 2025 nflverse PBP.

Distinguishes defensive/special-teams score candidates and 2-point events.
No ESPN D/ST points are assigned.
"""
import duckdb,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
cols={r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
optional=["td_team","touchdown","return_touchdown","interception","fumble_lost","safety","two_point_conv_result","defensive_two_point_conv","play_type","desc"]
select=", ".join(f'"{c}"' if c in cols else f'NULL AS "{c}"' for c in optional)
sql=f"""
WITH p AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,
 {select},total_home_score hs,total_away_score a,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) ph,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) pa
 FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL
 AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
)
SELECT game_id,week,play_id,posteam,defteam,
 CASE WHEN hs>ph THEN home_team ELSE away_team END scoring_team,
 GREATEST(COALESCE(hs-ph,0),COALESCE(a-pa,0)) points,
 td_team,touchdown,return_touchdown,interception,fumble_lost,safety,
 two_point_conv_result,defensive_two_point_conv,play_type,
 LEFT("desc",180) description
FROM p WHERE (hs>ph OR a>pa)
AND (CASE WHEN hs>ph THEN home_team ELSE away_team END)=defteam
ORDER BY points DESC,week,game_id,play_id
"""
try:
 rows=con.execute(sql,[src]).fetchall()
except Exception as exc:
 sys.exit("Defteam scoring audit failed: "+str(exc))
names=[c[0] for c in con.description]
events=[dict(zip(names,r)) for r in rows]
counts={}
for e in events:
 k=str(e["points"])+"pt"
 counts[k]=counts.get(k,0)+1
print(json.dumps({"defteam_scoring_events":len(events),"by_points":counts,
"two_point_events":[e for e in events if e["points"]==2],
"six_point_examples":[e for e in events if e["points"]==6][:18],
"warnings":["The scoring change may be recorded on a later row than the original event.",
"Do not equate defteam relation with ESPN defensive or special-teams scoring without validating play descriptions.",
"No fantasy points, live website, rankings, projections, or model weights changed."]},indent=2))
