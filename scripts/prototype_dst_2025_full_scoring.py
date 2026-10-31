#!/usr/bin/env python3
"""Read-only provisional 2025 D/ST scoring prototype; no production writes."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
fields=["game_id","week","play_id","home_team","away_team","posteam","defteam","play_type","desc","sack","interception","fumble_lost","fumble_recovery_1_team","fumble_recovery_2_team","total_home_score","total_away_score"]
sel=", ".join('"'+c+'"' if c in cols else 'NULL AS "'+c+'"' for c in fields)
rows=db.execute(f"""SELECT {sel} FROM read_parquet(?) WHERE season=2025
AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL AND play_id IS NOT NULL
AND COALESCE(play_type,'') <> 'GAME' AND (posteam IS NOT NULL OR defteam IS NOT NULL)
ORDER BY game_id,play_id""",[src]).fetchall()
stats=collections.defaultdict(collections.Counter); prev={}; exceptions=[]
for game,week,pid,home,away,off,defteam,typ,desc,sack,interception,fumble,r1,r2,hs,aws in rows:
 for team in (home,away):stats[(week,game,team)]
 if defteam:
  s=stats[(week,game,defteam)]
  s["sacks"]+=int(sack==1)
  s["interceptions"]+=int(interception==1)
  s["confirmed_defensive_fumble_recoveries"]+=int(fumble==1 and defteam in (r1,r2))
  d=(desc or "").upper()
  if typ in ("punt","field_goal","extra_point") and "BLOCKED" in d:s["blocked_kick_candidates"]+=1
 if hs is None or aws is None:continue
 old=prev.get(game,(hs,aws));prev[game]=(hs,aws)
 dh=hs-old[0];da=aws-old[1]
 if dh<=0 and da<=0:continue
 if dh>0 and da>0:continue
 scorer=home if dh>0 else away; pts=int(max(dh,da))
 if scorer not in (home,away):continue
 opponent=away if scorer==home else home
 if scorer==off and typ!="kickoff":
  stats[(week,game,opponent)]["provisional_points_allowed"]+=pts
 elif scorer==defteam:
  s=stats[(week,game,scorer)]
  d=(desc or "").upper()
  if pts==6:
   s["defensive_td" if typ in ("pass","run") else "special_teams_td"]+=1
  elif pts==2:
   s["safeties" if "SAFETY" in d else "defensive_two_point_conversions"]+=1
 elif typ=="kickoff" and pts==6 and scorer==off:
  # nflverse records the receiving team as posteam on these kickoff returns.
  stats[(week,game,scorer)]["special_teams_td"]+=1
  # A kickoff return TD is special-teams points allowed by the kicking team.
  stats[(week,game,opponent)]["provisional_points_allowed"]+=pts
 else:
  exceptions.append({"game_id":game,"play_id":pid,"points":pts,"play_type":typ,"scorer":scorer,"posteam":off,"defteam":defteam})
def pa_score(p):
 if p==0:return 5
 if p<=6:return 4
 if p<=13:return 3
 if p<=17:return 1
 if p<=27:return 0
 if p<=34:return -1
 if p<=45:return -3
 return -5
out=[]
for (week,game,team),s in sorted(stats.items()):
 pa=s["provisional_points_allowed"]
 score=(s["sacks"]+2*s["interceptions"]+2*s["confirmed_defensive_fumble_recoveries"]
 +2*s["blocked_kick_candidates"]+6*(s["defensive_td"]+s["special_teams_td"])
 +2*(s["safeties"]+s["defensive_two_point_conversions"])+pa_score(pa))
 out.append({"week":week,"game_id":game,"defense":team,"provisional_dst_points":score,
 "provisional_points_allowed":pa,**dict(s)})
print(json.dumps({"team_games":len(out),"scoring_rules":{"sack":1,"interception":2,"confirmed_fumble_recovery":2,"blocked_punt_or_fg_candidate":2,"defensive_or_special_teams_td":6,"safety":2,"defensive_two_point_conversion":2,"points_allowed_tiers":"0:+5, 1-6:+4, 7-13:+3, 14-17:+1, 18-27:0, 28-34:-1, 35-45:-3, 46+:-5"},
"totals":{"sacks":sum(s["sacks"] for s in stats.values()),"interceptions":sum(s["interceptions"] for s in stats.values()),"confirmed_defensive_fumble_recoveries":sum(s["confirmed_defensive_fumble_recoveries"] for s in stats.values()),"blocked_punt_or_fg_candidates":sum(s["blocked_punt_or_fg_candidates"] for s in stats.values()),"defensive_td":sum(s["defensive_td"] for s in stats.values()),"special_teams_td":sum(s["special_teams_td"] for s in stats.values()),"kickoff_return_td_expected_extra":5,"safeties":sum(s["safeties"] for s in stats.values()),"defensive_two_point_conversions":sum(s["defensive_two_point_conversions"] for s in stats.values())},
"unresolved_scoring_events":exceptions[:30],"unresolved_event_count":len(exceptions),
"sample_team_games":out[:12],"cautions":["PROVISIONAL: not ESPN-validated; points allowed on conversions following defensive/special teams scores and other ESPN-specific exceptions require review.","Do not use these fantasy scores for production projections or accuracy claims.","No outputs saved; no live site, rankings, projections or model weights changed."]},indent=2))
