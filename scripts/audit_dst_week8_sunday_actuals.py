#!/usr/bin/env python3
"""DATA DADDY Week 8 D/ST completed-game audit, excluding Monday CHI-SEA.
Read-only: writes a review JSON/CSV; never edits website or frozen projections.
"""
import csv,json,pathlib,urllib.request
WEEK=8;YEAR=2026
ROOT=pathlib.Path("projection-model/validation")
OUT=ROOT/"dst_2026_week8_sunday_actuals_review.json"
CSV=ROOT/"dst_2026_week8_sunday_accuracy_review.csv"
TEAMS={"ARI":"Cardinals","ATL":"Falcons","BAL":"Ravens","BUF":"Bills","CAR":"Panthers","CHI":"Bears","CIN":"Bengals","CLE":"Browns","DAL":"Cowboys","DEN":"Broncos","DET":"Lions","GB":"Packers","HOU":"Texans","IND":"Colts","JAX":"Jaguars","KC":"Chiefs","LV":"Raiders","LAC":"Chargers","LA":"Rams","MIA":"Dolphins","MIN":"Vikings","NE":"Patriots","NO":"Saints","NYG":"Giants","NYJ":"Jets","PHI":"Eagles","PIT":"Steelers","SF":"49ers","SEA":"Seahawks","TB":"Buccaneers","TEN":"Titans","WAS":"Commanders"}
# These are the exact frozen website V2 top 15, not regenerated postgame.
FROZEN=[("LA",6.67),("CHI",6.62),("ATL",6.55),("PIT",6.50),("TB",6.47),("JAX",6.21),("CIN",6.20),("CLE",6.19),("NE",6.13),("DET",6.05),("SEA",6.03),("LV",5.53),("MIN",5.29),("LAC",5.28),("DEN",5.20)]
def fetch(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {"User-Agent":"Mozilla/5.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=45) as f:return json.load(f)
board=fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=8")
finished=set();games=[]
for event in board.get("events",[]):
 competition=(event.get("competitions") or [{}])[0]
 competitors=competition.get("competitors") or []
 if not event.get("status",{}).get("type",{}).get("completed") or len(competitors)!=2:continue
 names=[c.get("team",{}).get("abbreviation") for c in competitors]
 # ESPN's LAR/WSH aliases need mapping for the preview's LA/WAS names.
 names=["LA" if x=="LAR" else "WAS" if x=="WSH" else x for x in names]
 if set(names)=={"CHI","SEA"}:continue
 if not all(x in TEAMS for x in names):continue
 finished.update(names);games.append({"teams":names,"event_id":event.get("id")})
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
players=fetch(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}/players?view=kona_player_info",headers)
def tier(n):
 if n==0:return 5
 if n<=6:return 4
 if n<=13:return 3
 if n<=17:return 1
 if n<=27:return 0
 if n<=34:return -1
 if n<=45:return -3
 return -5
actual={}
for player in players:
 if player.get("defaultPositionId")!=16:continue
 name=(player.get("fullName") or "").replace(" D/ST","")
 team=next((k for k,v in TEAMS.items() if v==name),None)
 if not team or team not in finished:continue
 entries=[x for x in player.get("stats",[]) if x.get("seasonId")==YEAR and x.get("scoringPeriodId")==WEEK and x.get("statSourceId")==0 and x.get("statSplitTypeId")==1 and x.get("stats")]
 if len(entries)!=1:continue
 st=entries[0]["stats"];v=lambda key:float(st.get(str(key),0))
 if "120" not in st:continue
 # Reconstructed ESPN standard D/ST scoring. Official league settings can differ.
 score=v(99)+2*v(95)+2*v(96)+2*v(97)+6*v(105)+2*v(98)+2*v(205)+tier(v(120))
 actual[team]={"actual_ppr":round(score,2),"sacks":v(99),"interceptions":v(95),"fumble_recoveries":v(96),"blocked_kicks":v(97),"dst_touchdowns":v(105),"points_allowed":v(120),"source":"ESPN fantasy raw D/ST stat IDs"}
rows=[]
for rank,(team,proj) in enumerate(FROZEN,1):
 a=actual.get(team)
 rows.append({"rank":rank,"defense":team,"projected_ppr":proj,"actual_ppr":a["actual_ppr"] if a else None,
 "absolute_error":round(abs(proj-a["actual_ppr"]),2) if a else None,
 "status":"FINAL" if a else ("FINAL_MISSING_STATS" if team in finished else "NOT_FINAL")})
scored=[r for r in rows if r["actual_ppr"] is not None]
ROOT.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"week":WEEK,"season":YEAR,"completed_games":games,"actuals":actual,"ranked":rows,
 "notes":["Monday CHI-SEA excluded even if it becomes final","ESPN raw stats reconstructed with fixed standard scoring, not verified league fantasy points","No frozen projection or site file changed"],"production_changed":False},indent=2)+"\n")
with CSV.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({"status":"GREEN","completed_games":len(games),"completed_defenses":len(finished),
 "ranked_with_actuals":len(scored),"ranked_pending":[r["defense"] for r in rows if r["actual_ppr"] is None],
 "mae":round(sum(r["absolute_error"] for r in scored)/len(scored),3) if scored else None,
 "ranked":rows,"json":str(OUT),"csv":str(CSV),"production_changed":False},indent=2))
