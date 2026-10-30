#!/usr/bin/env python3
"""Read-only 2025 NFL scoreboard reconstruction sanity check.

Uses monotonic home_score/away_score fields. Compares final observed scores
against nflverse game-level final score fields when available. Does not
calculate ESPN D/ST points allowed or change any files.
"""
import json, sys, duckdb
source = sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
try:
    cols={r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[source]).fetchall()}
    required={"game_id","season","week","play_id","home_score","away_score"}
    if not required.issubset(cols):
        sys.exit("Missing fields: "+", ".join(sorted(required-cols)))
    rows=con.execute("""
      WITH ordered AS (
        SELECT game_id, week, play_id, home_score, away_score,
          ROW_NUMBER() OVER(PARTITION BY game_id ORDER BY play_id DESC) rn
        FROM read_parquet(?)
        WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
      )
      SELECT game_id,week,home_score,away_score
      FROM ordered WHERE rn=1 ORDER BY game_id
    """,[source]).fetchall()
    if {"total_home_score","total_away_score"}.issubset(cols):
        finals=con.execute("""
          SELECT game_id, MAX(total_home_score), MAX(total_away_score)
          FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
          GROUP BY game_id
        """,[source]).fetchall()
        by_game={r[0]:(r[1],r[2]) for r in finals}
        mismatches=[{"game_id":g,"last_home":h,"last_away":a,
                     "max_total_home":by_game[g][0],"max_total_away":by_game[g][1]}
                    for g,w,h,a in rows if (h,a)!=by_game.get(g)]
    else:
        mismatches=[]
except Exception as exc:
    sys.exit("Scoreboard sanity check failed: "+str(exc))
print(json.dumps({
    "games":len(rows),
    "final_score_comparison_available":{"total_home_score","total_away_score"}.issubset(cols),
    "mismatch_count":len(mismatches),
    "mismatch_examples":mismatches[:10],
    "sample_final_scores":[{"game_id":g,"week":w,"home":h,"away":a} for g,w,h,a in rows[:5]],
    "warnings":["Comparison to MAX(total_*_score) is a diagnostic, not an independent official score check.",
                "No ESPN D/ST points allowed or fantasy points computed.",
                "No files, rankings, projections or model weights changed."]
},indent=2))
