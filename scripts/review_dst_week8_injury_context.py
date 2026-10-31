#!/usr/bin/env python3
"""Read-only Week 8 D/ST injury-context research snapshot.
Sources: NFL Week 8 injury reporting as of Oct 30, 2026.
Statuses are snapshots, NOT Sunday inactives. No scoring changes.
"""
import json,pathlib
records=[
 {"defense":"PIT","opponent":"CLE","player":"Tytus Howard","position":"OL","status":"QUESTIONABLE","detail":"concussion","source":"https://steelersdepot.com/2026/10/browns-week-8-friday-injury-report-key-offensive-starter-two-others-questionable/"},
 {"defense":"NE","opponent":"MIA","player":"Kadyn Proctor","position":"OL","status":"OUT","detail":"concussion","source":"https://www.nfl.com/news/nfl-week-8-injury-report-2026-season"},
 {"defense":"ATL","opponent":"TB","player":"Luke Goedeke","position":"OT","status":"DID_NOT_PRACTICE","detail":"practice report only; game status not confirmed by this record","source":"https://www.nfl.com/injuries/league/2026/REG8"},
 {"defense":"BUF","opponent":"BAL","player":"Lamar Jackson","position":"QB","status":"FULL_PRACTICE","detail":"ankle; practice participation is not a final active designation","source":"https://www.nfl.com/news/nfl-week-8-injury-report-2026-season"},
 {"defense":"WAS","opponent":"PHI","player":"DeVonta Smith","position":"WR","status":"OUT","detail":"hamstring","source":"https://www.nfl.com/news/nfl-week-8-injury-report-2026-season"}
]
out=pathlib.Path("projection-model/validation/dst_2026_week8_injury_context_review.json")
out.parent.mkdir(parents=True,exist_ok=True)
payload={"week":8,"as_of":"2026-10-30","status":"REVIEW_ONLY","coverage":"SELECTED VERIFIED EXAMPLES ONLY; NOT A COMPLETE LEAGUE AUDIT","records":records,"production_changed":False,
 "cautions":["Check Sunday official inactives before kickoff","Do not infer starter substitutions or points adjustments from practice participation","No injury-based model weights have been validated"]}
out.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"status":"GREEN","saved":str(out),"verified_examples":len(records),"production_changed":False,"next_step":"Review complete official statuses and inactive lists before any proposed model adjustment"},indent=2))
