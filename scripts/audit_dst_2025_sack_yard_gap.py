#!/usr/bin/env python3
"""Read-only audit: detect sack-yard omissions in 2025 run/pass yard sums."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
fields=["game_id","week","posteam","defteam","play_type","yards_gained","sack","yards_after_catch","desc"]
select=", ".join('"'+x+'"' if x in cols else 'NULL AS "'+x+'"' for x in fields)
rows=db.execute(f"""SELECT {select} FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME' ORDER BY game_id,play_id""",[src]).fetchall()
stats=collections.defaultdict(lambda:collections.Counter());examples=[]
for game,week,off,defteam,typ,yards,sack,yac,desc in rows:
 if not off or not defteam or typ not in ("run","pass"):continue
 s=stats[(game,off)]
 s["play_yards"]+=yards or 0
 if sack==1:
  s["sack_plays"]+=1
  s["sack_yards_included"]+=yards or 0
  if yards is None or yards==0:
   s["zero_or_missing_sack_yard_plays"]+=1
   if len(examples)<25:examples.append({"game_id":game,"offense":off,"play_type":typ,"yards_gained":yards,"description":(desc or "")[:220]})
sample=[{"game_id":g,"offense":o,**dict(s)} for (g,o),s in sorted(stats.items()) if g in ("2025_01_BAL_BUF","2025_01_ARI_NO")]
print(json.dumps({"sample_games":sample,"all_games_zero_or_missing_sack_yard_plays":sum(s["zero_or_missing_sack_yard_plays"] for s in stats.values()),"examples":examples,"note":"Read-only investigation; does not change fantasy scores or yards allowed."},indent=2))
