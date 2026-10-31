#!/usr/bin/env python3
"""Read-only 2026 Week 8 QB/OL injury status audit from NFL Friday game designations.
NFL article updated Oct 30, 2026. No absence is inferred for unlisted players.
Monday Bears/Seahawks report is pending; no model adjustment.
"""
import json,pathlib
source="https://fantasy-www.nfl.com/news/nfl-week-8-injury-report-2026-season"
slate=[["BAL","BUF"],["TEN","CIN"],["ARI","DAL"],["MIN","DET"],["IND","JAX"],["LV","NYJ"],["CLE","PIT"],["ATL","TB"],["LAC","LA"],["KC","DEN"],["NE","MIA"],["PHI","WAS"],["CHI","SEA"]]
ol=[["BAL","BUF","Olaivavega Ioane","G","OUT"],["BUF","BAL","Spencer Brown","OT","QUESTIONABLE"],["ARI","DAL","Jon Gaines II","OL","OUT"],["ARI","DAL","Hjalte Froholdt","OL","QUESTIONABLE"],["LV","NYJ","Jackson Powers-Johnson","OL","QUESTIONABLE"],["NYJ","LV","Max Mitchell","OL","OUT"],["NYJ","LV","Dylan Parham","OL","QUESTIONABLE"],["CLE","PIT","Tytus Howard","OT","QUESTIONABLE"],["ATL","TB","Cameron Williams","OT","QUESTIONABLE"],["TB","ATL","Luke Goedeke","OT","QUESTIONABLE"],["LAC","LA","Kayode Awosika","G","OUT"],["LA","LAC","Coleman Shelton","OL","QUESTIONABLE"],["DEN","KC","Garett Bolles","OT","QUESTIONABLE"],["MIA","NE","Kadyn Proctor","OL","OUT"]]
qb=[{"team":"BAL","player":"Lamar Jackson","status":"CLEARED_TO_PLAY","source":"https://www.nfl.com/news/ravens-qb-lamar-jackson-ankle-will-return-sunday-vs-bills-after-three-game-absence"}]
by_team={t:[] for game in slate for t in game}
for team,opponent,player,position,status in ol:
 by_team[team].append({"player":player,"position":position,"game_status":status,"source":source})
out=[]
for away,home in slate:
 for defense,opponent in ((away,home),(home,away)):
  out.append({"defense":defense,"opponent_offense":opponent,
    "opponent_ol_designations":by_team[opponent],
    "opponent_qb_updates":[r for r in qb if r["team"]==opponent],
    "source_status":"MONDAY_REPORT_PENDING" if opponent in ("CHI","SEA") else "FRIDAY_REPORT_REVIEWED",
    "interpretation":"No reported OL OUT/QUESTIONABLE in NFL Friday list" if not by_team[opponent] else "OL availability requires review",
    "production_changed":False})
assert len(out)==26
dest=pathlib.Path("projection-model/validation/dst_2026_week8_qb_ol_audit_review.json")
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps({"week":8,"as_of":"2026-10-30","source":source,
 "coverage":"All 13 remaining games; NFL final Friday game statuses; Monday report pending",
 "defenses":out,"notes":["Listed designations are NOT confirmed Sunday inactives",
 "Unlisted QBs are NOT verified healthy or starting","No injury model coefficients have been validated",
 "Recheck official inactive lists 90 minutes before kickoff"],"production_changed":False},indent=2)+"\n")
print(json.dumps({"status":"GREEN","games":len(slate),"defenses":len(out),
 "offensive_line_designations":len(ol),"monday_report_pending":["CHI","SEA"],
 "saved":str(dest),"production_changed":False},indent=2))
