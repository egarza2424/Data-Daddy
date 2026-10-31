#!/usr/bin/env python3
"""Export provisional 2025 D/ST team-game scores for offline ESPN comparison."""
import contextlib,csv,io,json,runpy,sys,pathlib
script=pathlib.Path(__file__).with_name("prototype_dst_2025_full_scoring.py")
capture=io.StringIO()
with contextlib.redirect_stdout(capture):
 runpy.run_path(str(script),run_name="__main__")
# Prototype emits samples only; use the same in-memory stats from run_path.
# Re-run with globals captured (runpy returns the stats dictionary).
with contextlib.redirect_stdout(io.StringIO()):
 g=runpy.run_path(str(script),run_name="__main__")
stats=g["stats"];pa_score=g["pa_score"]
dest=pathlib.Path("projection-model/validation/dst_2025_provisional_scores.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
fields=["week","game_id","defense","provisional_dst_points","provisional_points_allowed","sacks","interceptions","confirmed_defensive_fumble_recoveries","blocked_kick_candidates","defensive_td","special_teams_td","safeties","defensive_two_point_conversions"]
with dest.open("w",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
 for (week,game,team),s in sorted(stats.items()):
  pa=s["provisional_points_allowed"]
  points=(s["sacks"]+2*s["interceptions"]+2*s["confirmed_defensive_fumble_recoveries"]+2*s["blocked_kick_candidates"]+6*(s["defensive_td"]+s["special_teams_td"])+2*(s["safeties"]+s["defensive_two_point_conversions"])+pa_score(pa))
  writer.writerow({"week":week,"game_id":game,"defense":team,"provisional_dst_points":points,"provisional_points_allowed":pa,**{k:s[k] for k in fields[5:]}})
print(json.dumps({"csv_path":str(dest),"team_games":len(stats),"status":"PROVISIONAL — for offline ESPN comparison only","note":"CSV generated locally; not committed, not published; no live model or website changes."},indent=2))
