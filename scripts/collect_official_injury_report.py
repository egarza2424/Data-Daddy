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
    # Extract names only as review candidates. Encoded NFL markup is not a
    # sufficient basis for a verified OUT or teammate opportunity adjustment.
    candidates = []
    for snippet in snippets:
        for raw in re.findall(r'title=\\\\?"([^"\\\\]+)\\\\?"', snippet):
            name = raw.strip()
            if name and name not in candidates:
                candidates.append(name)

    result = {
        "season": args.season, "week": args.week,
        "source_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_status": "official_source_text_unresolved_player_identity",
        "automatically_verified_outs": [],
        "out_text_observations": snippets,
        "unverified_name_candidates": candidates,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"Captured {len(snippets)} official-source OUT snippets; no player availability changed.")

if __name__ == "__main__":
    main()
