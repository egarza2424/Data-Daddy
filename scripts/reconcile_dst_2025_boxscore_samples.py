#!/usr/bin/env python3
"""Read-only targeted reconciliation of nflverse offense yards to verified 2025 box scores."""
import duckdb,json,collections,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
targets={("2025_01_MIA_IND","MIA"):211,("2025_05_DET_CIN","DET"):365,("2025_01_ARI_NO","ARI"):276,("2025_01_ARI_NO","NO"):315}
db=duckdb.connect()
rows=db.execute("""SELECT game_id,play_id,posteam,play_type,yards_gained,sack,fumble,"desc" FROM read_parquet(?)
WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IN ('2025_01_MIA_IND','2025_05_DET_CIN','2025_01_ARI_NO')
ORDER BY game_id,play_id""",[src]).fetchall()
summary=collections.defaultdict(lambda:collections.Counter());flagged=[]
for game,pid,off,typ,yards,sack,fumble,desc in rows:
 if (game,off) not in targets or typ not in ("run","pass"):continue
 key=(game,off);s=summary[key];s["total"]+=yards or 0;s["plays"]+=1
 if sack==1:s["sacks"]+=1;s["sack_yards"]+=yards or 0
 if fumble==1:
  s["fumble_plays"]+=1
  flagged.append({"game_id":game,"offense":off,"play_id":pid,"play_type":typ,"yards_gained":yards,"sack":sack,"description":(desc or "")[:260]})
out=[{"game_id":g,"offense":o,"official_total":v,"calculated_total":summary[(g,o)]["total"],"difference":summary[(g,o)]["total"]-v,"sacks":summary[(g,o)]["sacks"],"sack_yards_included":summary[(g,o)]["sack_yards"],"fumble_plays":summary[(g,o)]["fumble_plays"]} for (g,o),v in targets.items()]
print(json.dumps({"comparisons":out,"fumble_plays_for_review":flagged,"note":"Independent official totals entered as fixed reference values; read-only, no scoring changes."},indent=2))
