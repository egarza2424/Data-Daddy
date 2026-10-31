#!/usr/bin/env python3
"""Read-only Week 8 D/ST opponent pass protection and turnover risk audit.
2026 weeks 1-7 nflverse play-by-play; NO injuries inferred and NO model changes.
"""
import collections,csv,json,pathlib
import duckdb
source="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet"
db=duckdb.connect()
rows=db.execute("""SELECT week,game_id,posteam,play_id,COALESCE(pass_attempt,0),COALESCE(sack,0),COALESCE(interception,0),COALESCE(fumble_lost,0),COALESCE(qb_dropback,0)
FROM read_parquet(?) WHERE season=2026 AND week BETWEEN 1 AND 7
AND game_id IS NOT NULL AND play_id IS NOT NULL AND posteam IS NOT NULL
AND (COALESCE(qb_dropback,0)=1 OR COALESCE(pass_attempt,0)=1 OR COALESCE(sack,0)=1 OR COALESCE(interception,0)=1 OR COALESCE(fumble_lost,0)=1)""",[source]).fetchall()
team=collections.defaultdict(lambda:collections.Counter())
games=collections.defaultdict(set)
seen=set()
for w,g,t,p,pa,s,inter,f,drop in rows:
 key=(g,p)
 if key in seen:continue
 seen.add(key);games[t].add(g)
 team[t]["dropbacks"]+=int(drop==1 or pa==1 or s==1)
 team[t]["sacks_allowed"]+=int(s==1)
 team[t]["interceptions"]+=int(inter==1)
 team[t]["fumbles_lost_on_selected_plays"]+=int(f==1)
# Read actual slate from preview (review-only), do not import script (it runs network).
import ast
tree=ast.parse(pathlib.Path("scripts/preview_dst_2026_week8_v1.py").read_text())
slate=None
for n in tree.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="games" for t in n.targets):
  slate=ast.literal_eval(n.value)
if slate is None:raise SystemExit("No Week 8 preview slate found")
output=[]
for away,home in slate:
 for defense,offense in ((away,home),(home,away)):
  x=team[offense];n=len(games[offense]);d=x["dropbacks"]
  if n<5 or d<100:raise SystemExit(f"Insufficient offensive sample for {offense}: games={n} dropbacks={d}")
  output.append({"defense":defense,"opponent_offense":offense,"opponent_games":n,"opponent_dropbacks":d,
    "opponent_sacks_allowed_per_game":round(x["sacks_allowed"]/n,2),
    "opponent_sack_rate_pct":round(100*x["sacks_allowed"]/d,2),
    "opponent_interceptions_per_game":round(x["interceptions"]/n,2),
    "opponent_pass_play_fumbles_lost_per_game":round(x["fumbles_lost_on_selected_plays"]/n,2),
    "qb_injury_status":"NOT_VERIFIED","offensive_line_injuries":"NOT_VERIFIED","status":"REVIEW_ONLY"})
output.sort(key=lambda r:(-r["opponent_sack_rate_pct"],-r["opponent_interceptions_per_game"]))
dest=pathlib.Path("projection-model/validation/dst_2026_week8_opponent_risk_review.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
print(json.dumps({"week":8,"defenses":len(output),"highest_opponent_sack_rates":output[:12],"saved":str(dest),
"cautions":["Sack rates and turnovers from prior completed games only","Fumbles here limited to selected passing/dropback plays, not all offensive fumbles","QB and offensive line injuries intentionally NOT VERIFIED; check official injury reports separately","No fantasy score adjustments or production changes"],"production_changed":False},indent=2))
