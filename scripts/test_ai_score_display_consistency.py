"""Guard against AI Score drift between Rankings and Projections.

Both displays must use the same shared live scoring helper. The historical
projection snapshot model_score must never be displayed as the current score.
"""
from pathlib import Path
import re

app = Path("app.js").read_text(encoding="utf-8")
start = app.index("function renderProjectionBoard()")
end = app.index("\nfunction ", start + 1)
projection = app[start:end]
start = app.index("function getPositionRankings(")
end = app.index("\nfunction ", start + 1)
ranking = app[start:end]

checks = {
    "shared AI Score helper exists":
        "function getDisplayedAiScore(player, profile)" in app,
    "shared helper uses calculateScore":
        bool(re.search(r"function getDisplayedAiScore\(player, profile\)\s*\{\s*return player \? calculateScore\(player, profile\) : NaN;", app)),
    "rankings use shared AI Score helper":
        "score: getDisplayedAiScore(player, profile)" in ranking,
    "projections use shared AI Score helper":
        "const aiScore = getDisplayedAiScore(player, profile);" in projection,
    "projections use current risk profile":
        'const profile = riskSelect?.value || "balanced";' in projection,
    "projections do not display stale snapshot AI Score":
        not bool(re.search(r"(?:const\s+aiScore\s*=|\.textContent\s*=)[^;]*projection\.model_score", projection)),
    "projections use live AI ranking":
        "getPlayerPositionRank(player, profile)" in projection,
}
for label, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + label)
if not all(checks.values()):
    raise SystemExit("AI Score consistency regression detected.")
