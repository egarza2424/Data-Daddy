#!/usr/bin/env python3
"""Read-only inspection of nflverse fumble-yard fields for two D/ST box-score mismatches."""
import duckdb,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
wanted=["game_id","play_id","posteam","defteam","play_type","yards_gained","sack","fumble","fumble_lost","fumble_recovery_1_yards","fumble_recovery_2_yards","fumble_recovery_1_team","fumble_recovery_2_team","lateral_recovery","lateral_recovery_yards","return_yards","drive","desc"]
selected=[c for c in wanted if c in cols]
sql=", ".join('"'+c+'"' for c in selected)
rows=db.execute(f"""SELECT {sql} FROM read_parquet(?) WHERE (game_id='2025_01_MIA_IND' AND play_id=898) OR (game_id='2025_05_DET_CIN' AND play_id=669)""",[src]).fetchall()
print(json.dumps({"available_columns":selected,"plays":[dict(zip(selected,row)) for row in rows],"note":"Read-only investigation; no historical or production scoring adjustments."},indent=2,default=str))
