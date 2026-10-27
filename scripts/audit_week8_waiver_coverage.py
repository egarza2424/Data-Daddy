"""Review-only diagnostic for Week 8 waiver candidate coverage.

Uses the same player_lookup/opportunity_volume and scheduled-game exclusion
as build_waiver_wire.py. Does not modify scores, eligibility or live outputs.
"""
import csv
import json
from pathlib import Path

from build_waiver_wire import fetch_nfl_schedule, normalized_name

SOURCE = Path("nfl-stats.json")
OUT = Path("projection-model/validation/2026-week8-waiver-coverage-diagnostic.csv")
WATCH = ["Antonio Williams", "Caleb Douglas", "Chig Okonkwo", "Seth McGowan"]
def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    season = int(data["season"])
    target = int(data["target_week"])
    players = data.get("player_lookup", {})
    opp = data.get("opportunity_volume", {})
    weeks, _, _, _ = fetch_nfl_schedule(season)
    rows = []
    for name in WATCH:
        matched = [(pid,p) for pid,p in players.items()
                   if normalized_name(p.get("name")) == normalized_name(name)]
        if not matched:
            rows.append({"name":name,"source_player_present":False,
                         "reason":"ABSENT_FROM_PLAYER_LOOKUP"})
            continue
        for pid,p in matched:
            games = sorted((g for g in opp.get(pid,{}).get("games",[])
                            if int(g.get("season") or 0)==season),
                           key=lambda g:int(g.get("week") or 0),reverse=True)
            latest = int(games[0].get("week") or 0) if games else None
            team = str(p.get("team") or "").upper()
            scheduled = "LA" if team=="LAR" else team
            missed = [w for w in range((latest or 0)+1,target)
                      if w in weeks.get(scheduled,set())] if latest else []
            reason = ("NO_SEASON_OPPORTUNITY_GAMES" if not games else
                      "SKIPPED_AFTER_MISSED_SCHEDULED_WEEK" if missed else
                      "PASSED_INITIAL_SOURCE_FILTER")
            rows.append({"name":name,"source_player_present":True,
                         "player_id":pid,"team":team,"position":p.get("position"),
                         "latest_recorded_week":latest,
                         "missed_scheduled_weeks":";".join(map(str,missed)),
                         "reason":reason,
                         "note":"Later ownership/availability checks may still exclude player"})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    columns=["name","source_player_present","player_id","team","position",
             "latest_recorded_week","missed_scheduled_weeks","reason","note"]
    with OUT.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    for r in rows: print(r)
    print("Saved",OUT,"— review only; no live changes")
if __name__=="__main__": main()
