#!/usr/bin/env python3
"""Read-only Week 8 high-impact identity and participation evidence from nflverse.
No inferred DNP from absent rows or zero PPR. No production edits.
"""
import csv,json,pathlib,collections
import duckdb
base=pathlib.Path("projection-model/validation")
priority=json.loads((base/"week8_sunday_high_impact_participation_priority.json").read_text())["priority"]
names={"Omar Cooper Jr.","KeAndre Lambert-Smith","Travis Hunter","Dontayvion Wicks","Colby Parkinson","Konata Mumpfield"}
url="https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[url]).fetchall()}
wanted=[c for c in ("season","week","player_display_name","player_id","team","position","fantasy_points_ppr","targets","receptions","receiving_yards","carries","rushing_yards","snap_count","offense_snaps") if c in cols]
rows=db.execute("SELECT "+",".join(wanted)+" FROM read_parquet(?) WHERE season=2026 AND week=8",[url]).fetchall()
records=[dict(zip(wanted,r)) for r in rows]
def norm(v):
 import re
 return re.sub(r"\\s+(jr|sr|ii|iii|iv|v)$","",re.sub(r"\\s+"," ",re.sub(r"[.'’\\-]","",str(v or "").lower())).strip())
def team(v):return {"LA":"LAR","JAC":"JAX","WSH":"WAS"}.get(str(v).upper(),str(v).upper())
out=[]
for p in priority:
 if p["player"] not in names:continue
 matches=[r for r in records if norm(r.get("player_display_name"))==norm(p["player"])]
 same_team=[r for r in matches if team(r.get("team"))==team(p["team"])]
 out.append({"player":p["player"],"expected_team":p["team"],"expected_position":p["position"],"issue":p["issue"],"same_name_week8_rows":matches,"same_team_rows":same_team,"classification":"MATCH_REQUIRES_REVIEW" if same_team else "NO_MATCH_NOT_PROOF_OF_INACTIVITY"})
path=base/"week8_sunday_high_impact_nflverse_evidence.json"
path.write_text(json.dumps({"status":"REVIEW_ONLY","columns_available":wanted,"players":out,"warning":"Weekly stat feed is not a snap-count or official inactive source. Absence does not prove DNP."},indent=2,default=str)+"\n")
print(json.dumps({"status":"GREEN","players":out,"saved":str(path),"production_changed":False},indent=2,default=str))
