#!/usr/bin/env python3
"""Read-only 2025 scoring-event classification diagnostic for ESPN D/ST research.

Lists score increments and contextual play flags. Classification is provisional;
no ESPN points-allowed or fantasy scores are calculated.
"""
import duckdb, json, sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
cols={r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
required={"season","week","game_id","play_id","home_team","away_team","home_score","away_score","posteam","defteam"}
if not required.issubset(cols):
    sys.exit("Missing columns: "+", ".join(sorted(required-cols)))
optional=["td_team","touchdown","return_touchdown","interception","fumble_lost","safety","play_type","field_goal_result","extra_point_result","desc"]
select=", ".join((f'"{c}"' if c in cols else f'NULL AS "{c}"') for c in optional)
query=f"""
WITH p AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,
 home_score,away_score,{select},
 LAG(home_score,1,0) OVER(PARTITION BY game_id ORDER BY play_id) AS old_home,
 LAG(away_score,1,0) OVER(PARTITION BY game_id ORDER BY play_id) AS old_away
 FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL
)
SELECT game_id,week,play_id,
 CASE WHEN home_score>old_home THEN home_team WHEN away_score>old_away THEN away_team ELSE NULL END AS scoring_team,
 home_score-old_home AS home_delta,away_score-old_away AS away_delta,
 posteam,defteam,td_team,touchdown,return_touchdown,interception,
 fumble_lost,safety,play_type,field_goal_result,extra_point_result,
 LEFT("desc",160) AS description
FROM p WHERE home_score>old_home OR away_score>old_away
ORDER BY game_id,play_id
"""
try:
    rows=con.execute(query,[src]).fetchall()
except Exception as exc:
    sys.exit("Scoring event audit failed: "+str(exc))
names=[x[0] for x in con.description]
events=[dict(zip(names,r)) for r in rows]
unusual=[e for e in events if (e["home_delta"]>0 and e["away_delta"]>0)
         or max(e["home_delta"],e["away_delta"])>8]
different=[e for e in events if e["scoring_team"] != e["posteam"]]
print(json.dumps({
 "scoring_events":len(events),
 "scoring_team_differs_from_posteam":len(different),
 "unusual_score_deltas":len(unusual),
 "different_team_examples":different[:15],
 "unusual_examples":unusual[:10],
 "warnings":["Score changes may be recorded on later rows than the originating play; do not infer ESPN credit from this diagnostic.",
             "No ESPN points allowed, fantasy points, projections, rankings, model weights, or files changed."]
},indent=2))
