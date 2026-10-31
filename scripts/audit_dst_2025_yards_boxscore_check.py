#!/usr/bin/env python3
"""Read-only comparison of nflverse play-yard sums to nflverse game-level team totals."""
import duckdb,json,collections,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
wanted=["game_id","week","home_team","away_team","posteam","defteam","play_type","yards_gained","sack","home_total_yards","away_total_yards","home_rush_yards","away_rush_yards","home_pass_yards","away_pass_yards"]
print("Available game-total columns:",json.dumps([x for x in wanted[9:] if x in cols]))
expr=", ".join('"'+x+'"' if x in cols else 'NULL AS "'+x+'"' for x in wanted)
rows=db.execute(f"""SELECT {expr} FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME' ORDER BY game_id,play_id""",[src]).fetchall()
totals=collections.defaultdict(float);sacks=collections.defaultdict(float);game_refs={}
for row in rows:
 game,week,home,away,off,defteam,typ,yards,sack,*ref=row
 if typ in ("pass","run") and off and defteam:
  totals[(game,off)]+=yards or 0
  if sack==1:sacks[(game,off)]+=1
 game_refs[game]=(home,away,ref)
print(json.dumps({"games":len(game_refs),"team_games":len(totals),"summed_yards":sum(totals.values()),"sack_plays":sum(sacks.values()),"sample_offensive_team_totals":[{"game_id":g,"offense":t,"summed_yards":v,"sacks":sacks[(g,t)]} for (g,t),v in sorted(totals.items())[:16]],"note":"Audit only; compare samples to NFL box-score total offense. Do not add yardage fantasy points yet."},indent=2))
