#!/usr/bin/env python3
"""Read-only compare nflverse 2025 pass/run/sack aggregates to independent box scores."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
reference={("2025_01_MIA_IND","MIA"):{"rush":78,"gross_pass":146,"sack_loss":13,"net":211},("2025_05_DET_CIN","DET"):{"rush":118,"gross_pass":261,"sack_loss":14,"net":365}}
db=duckdb.connect()
rows=db.execute("""SELECT game_id,posteam,play_type,yards_gained,passing_yards,rushing_yards,sack,fumble,play_id,"desc" FROM read_parquet(?) WHERE season=2025 AND game_id IN ('2025_01_MIA_IND','2025_05_DET_CIN') ORDER BY game_id,play_id""",[src]).fetchall()
stats=collections.defaultdict(collections.Counter)
for game,off,typ,yards,py,ry,sack,fumble,pid,desc in rows:
 if (game,off) not in reference or typ not in ("run","pass"):continue
 s=stats[(game,off)];s["raw_yards"]+=yards or 0
 if typ=="run":s["run_play_yards"]+=yards or 0
 if typ=="pass":s["pass_play_yards"]+=yards or 0
 if py is not None:s["passing_yards_field"]+=py
 if ry is not None:s["rushing_yards_field"]+=ry
 if sack==1:s["sack_yards_field"]+=yards or 0;s["sack_count"]+=1
 if fumble==1:s["fumble_play_yards"]+=yards or 0
out=[]
for key,ref in reference.items():
 s=stats[key];g,o=key
 out.append({"game_id":g,"offense":o,"reference":ref,"nflverse":dict(s),"expected_net_from_boxscore_components":ref["rush"]+ref["gross_pass"]-ref["sack_loss"],"run_delta":s["run_play_yards"]-ref["rush"],"gross_pass_field_delta":s["passing_yards_field"]-ref["gross_pass"],"net_delta":s["raw_yards"]-ref["net"]})
print(json.dumps({"comparisons":out,"note":"Read-only component comparison; official box-score figures manually verified. No changes to scoring or production."},indent=2))
