#!/usr/bin/env python3
"""Audit Week 8 2026 D/ST preview matchups against ESPN schedule. Read-only."""
import json,urllib.request,collections,sys
from pathlib import Path
season=2026;week=8
url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2&week={week}&limit=100"
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=35) as f:data=json.load(f)
events=data.get("events",[])
if not events:raise SystemExit("RED: ESPN returned no Week 8 games; no changes made.")
espn_to_nfl={"WSH":"WAS","LAR":"LA","JAC":"JAX"}
def normalize(x):return espn_to_nfl.get(x,x)
official=[];completed=[]
for event in events:
 competitors=event.get("competitions",[{}])[0].get("competitors",[])
 away=next((c for c in competitors if c.get("homeAway")=="away"),None)
 home=next((c for c in competitors if c.get("homeAway")=="home"),None)
 if not away or not home:raise SystemExit("RED: Missing home/away data: "+str(event.get("id")))
 a=normalize(away["team"]["abbreviation"]);h=normalize(home["team"]["abbreviation"])
 official.append((a,h))
 if event.get("status",{}).get("type",{}).get("completed"):completed.append((a,h))
source=Path("scripts/preview_dst_2026_week8_v1.py").read_text()
import ast
tree=ast.parse(source)
planned=None
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="games" for t in node.targets):
  planned=ast.literal_eval(node.value)
if planned is None:raise SystemExit("RED: Could not inspect preview matchups")
planned=set(map(tuple,planned));official=set(official);remaining=official-set(completed)
teams={x for pair in official for x in pair}
all_teams=set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SF SEA TB TEN WAS".split())
result={"week":week,"espn_events":len(events),"planned_matchups":len(planned),"schedule_matches":planned==remaining,"missing_from_preview":[list(x) for x in sorted(remaining-planned)],"extra_in_preview":[list(x) for x in sorted(planned-remaining)],"espn_completed_games":[list(x) for x in sorted(completed)],"espn_bye_teams":sorted(all_teams-teams),"official_matchups":[{"away":a,"home":h} for a,h in sorted(official)],"production_changed":False}
print(json.dumps(result,indent=2))
if planned!=remaining:sys.exit("RED: Schedule mismatch. Do not publish preview until corrected.")
print("GREEN: Preview matchups and home/away match all remaining ESPN games; completed games excluded.")
