
"""Discover candidate NFL.com inactive reports.

Discovery only: does not confirm report completeness,
game coverage, or official player statuses.
"""

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

LISTING_URL = (
    "https://www.nfl.com/news/series/"
    "around-the-nfl-news"
)

OUTPUT = Path("data/nfl_inactive_report_candidates.json")


class ArticleLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_url = None
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        href = dict(attrs).get("href", "")
        url = urljoin(LISTING_URL, href)
        parsed = urlparse(url)

        if (
            parsed.netloc in {"www.nfl.com", "nfl.com"}
            and parsed.path.startswith("/news/")
        ):
            self.current_url = url
            self.text_parts = []

    def handle_data(self, data):
        if self.current_url:
            self.text_parts.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self.current_url:
            return

        title = " ".join(
            "".join(self.text_parts).split()
        )

        if title:
            self.links.append({
                "url": self.current_url,
                "title": title,
            })

        self.current_url = None
        self.text_parts = []


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(
        request, timeout=45
    ) as response:
        return response.read().decode(
            "utf-8", errors="replace"
        )


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--season", type=int, required=True)
    cli.add_argument("--week", type=int, required=True)
    args = cli.parse_args()

    html = fetch(LISTING_URL)

    parser = ArticleLinks()
    parser.feed(html)

    candidates = []
    seen = set()

    for article in parser.links:
        title = article["title"]
        url = article["url"]

        if not re.search(
            r"\binactives?\b",
            title,
            flags=re.IGNORECASE,
        ):
            continue

        week_match = re.search(
            r"\bweek[\s-]+(\d{1,2})\b",
            title,
            flags=re.IGNORECASE,
        )

        if not week_match:
            continue

        if int(week_match.group(1)) != args.week:
            continue

        if url in seen:
            continue

        season_pattern = (
            rf"\b{args.season}\b"
        )

        if not (
            re.search(season_pattern, title)
            or re.search(
                season_pattern,
                url,
            )
        ):
            continue

        seen.add(url)
        # The title identifies the week, but not
        # necessarily the season or publication date.
        # These are candidates, not verified reports.
        candidates.append({
            "title": title,
            "url": url,
            "week": args.week,
            "season": args.season,
            "verification_status": (
                "candidate_season_unverified"
            ),
        })

    result = {
        "requested_season": args.season,
        "requested_week": args.week,
        "listing_url": LISTING_URL,
        "retrieved_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Candidate reports found:",
        len(candidates),
    )

    for candidate in candidates:
        print(candidate["title"])
        print(candidate["url"])

    if not candidates:
        print(
            "No matching candidates found. "
            "The listing may have changed or "
            "the report may not be published yet."
        )


if __name__ == "__main__":
    main()
