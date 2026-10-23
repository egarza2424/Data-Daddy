"""Collect NFL.com's weekly injury article as a source-attributed review feed.

This is NOT a verified-out feed. Parsing ambiguous HTML must never automatically
change player availability or opportunity projections.
"""
import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--output", default="data/official_injury_report_observations.json")
    args = p.parse_args()
    url = f"https://www.nfl.com/news/nfl-week-{args.week}-injury-report-{args.season}-season"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DataDaddyInjuryAudit/1.0)"})
    with urllib.request.urlopen(req, timeout=35) as resp:
        if resp.status != 200:
            raise RuntimeError(f"NFL source returned HTTP {resp.status}")
        html = resp.read(3_000_000).decode("utf-8", errors="replace")
    parser = TextParser()
    parser.feed(html)
    text = "\n".join(parser.parts)
    if f"Week {args.week}" not in text or "injury report" not in text.lower():
        raise RuntimeError("Official NFL article identity could not be validated")
    # Keep snippets for review; team/player identity must be independently resolved.
    snippets = []
    for match in re.finditer(r"\bOUT\s*:", text, re.I):
        snippet = text[match.start():match.start()+500].split("\n")[0][:350]
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    if not snippets:
        raise RuntimeError("No explicit OUT labels parsed from NFL article")
    # Preserve bounded context around each OUT heading for team-section review.
    # This is audit evidence, not a verified player designation.
    out_section_context = []
    for match in re.finditer(r"\bOUT\s*:", text, re.I):
        before = text[max(0, match.start() - 350):match.start()]
        after = text[match.end():match.end() + 1000]
        out_section_context.append({
            "preceding_context": before[-350:],
            "following_context": after[:1000],
            "team_verified": False,
            "player_status_verified": False,
        })

    # Extract names only as review candidates. Encoded NFL markup is not a
    # sufficient basis for a verified OUT or teammate opportunity adjustment.
    candidates = []
    for snippet in snippets:
        for raw in re.findall(r'title=\\\\?"([^"\\\\]+)\\\\?"', snippet):
            name = raw.strip()
            if name and name not in candidates:
                candidates.append(name)

    # Candidate matching is diagnostic only. A name match does not establish
    # team, report section, game status, or confirmed absence.
    directory_path = Path("data/gameday_availability.json")
    def normalized_name(value):
        # Normalize punctuation and common suffixes, but never use fuzzy matching
        # to auto-confirm an OUT designation.
        parts = re.findall(r"[a-z0-9]+", str(value).casefold())
        while parts and parts[-1] in {"jr", "sr", "ii", "iii", "iv"}:
            parts.pop()
        return " ".join(parts)

    directory_matches = []
    if directory_path.exists():
        directory = json.loads(directory_path.read_text(encoding="utf-8"))
        players = directory.get("players", [])
        if isinstance(players, dict):
            players = list(players.values())
        for name in candidates:
            normalized = normalized_name(name)
            matches = []
            for player in players:
                if not isinstance(player, dict):
                    continue
                player_name = player.get("player_name") or player.get("full_name") or player.get("name") or ""
                if normalized_name(player_name) == normalized:
                    matches.append({
                        "player_id": str(player.get("player_id") or player.get("sleeper_id") or ""),
                        "player_name": player_name,
                        "team": player.get("team"),
                        "position": player.get("position"),
                    })
            directory_matches.append({
                "reported_name": name,
                "match_status": "unique_name_only" if len(matches) == 1 else ("ambiguous" if matches else "unmatched"),
                "matches": matches,
            })
    # Do not equate appearing anywhere in a truncated OUT snippet with OUT.
    # Retain candidate-level evidence for review; verified OUT stays empty.
    for item in directory_matches:
        item["status_verification"] = "not_verified"
        item["team_verification"] = "not_verified"
        item["eligible_for_projection_adjustment"] = False
    result = {
        "season": args.season, "week": args.week,
        "source_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_status": "official_source_text_unresolved_player_identity",
        "automatically_verified_outs": [],
        "out_text_observations": snippets,
        "out_section_context_unverified": out_section_context,
        "unverified_name_candidates": candidates,
        "directory_name_matches_unverified": directory_matches,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"Captured {len(snippets)} official-source OUT snippets; no player availability changed.")

if __name__ == "__main__":
    main()
