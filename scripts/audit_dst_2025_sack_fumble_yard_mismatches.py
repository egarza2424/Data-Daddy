#!/usr/bin/env python3
"""Read-only: inspect nflverse sack-fumble yardage fields and text mismatches."""
import duckdb,json,re,collections,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
extra=[x for x in ("sack_yards","passing_yards","rushing_yards","fumble_lost","fumble","ydstogo","yardline_100") if x in cols]
fields=["game_id","week","posteam","play_type","sack","yards_gained","desc"]+extra
select=", ".join('"'+x+'"' for x in fields)
rows=db.execute(f"""SELECT {select} FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18 AND sack=1 AND COALESCE(play_type,'') <> 'GAME' ORDER BY game_id,play_id""",[src]).fetchall()
examples=[];mismatch=[];zero=0
for row in rows:
 d=dict(zip(fields,row));yard=d["yards_gained"];description=d["desc"] or ""
 m=re.search(r'\bsacked\b[^.]{0,150}?\bfor\s+(-?\d+)\s+yards?',description,re.I)
 if yard==0 or yard is None:
  zero+=1
  if m and int(m.group(1))<0:mismatch.append({"game_id":d["game_id"],"offense":d["posteam"],"text_sack_yards":int(m.group(1)),**{k:d.get(k) for k in extra},"description":description[:220]})
  elif len(examples)<10:examples.append({"game_id":d["game_id"],"offense":d["posteam"],"description":description[:160]})
print(json.dumps({"available_additional_columns":extra,"sack_plays":len(rows),"zero_or_missing_yards_sacks":zero,"negative_sack_yards_in_text_but_zero_field":len(mismatch),"mismatches":mismatch[:35],"zero_yard_examples":examples,"note":"Diagnostic only. Descriptions are not an authoritative substitute for box scores; no production changes."},indent=2))
