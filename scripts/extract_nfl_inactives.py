
"""Extract team-specific NFL inactives from an NFL.com report.

Produces extraction candidates for validation.
Does not independently verify publication time or game IDs.
"""

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

SOURCE_URL = (
    "https://www.nfl.com/news/"
    "nfl-week-6-inactives-players-ruled-out-"
    "sunday-2026-season"
)

OUTPUT = Path("data/nfl_inactives_extracted.json")

TEAMS = {
    "CARDINALS", "FALCONS", "RAVENS", "BILLS",
    "PANTHERS", "BEARS", "BENGALS", "BROWNS",
    "COWBOYS", "BRONCOS", "LIONS", "PACKERS",
    "TEXANS", "COLTS", "JAGUARS", "CHIEFS",
    "RAIDERS", "CHARGERS", "RAMS", "DOLPHINS",
    "VIKINGS", "PATRIOTS", "SAINTS", "GIANTS",
    "JETS", "EAGLES", "STEELERS", "49ERS",
    "SEAHAWKS", "BUCCANEERS", "TITANS",
    "COMMANDERS",
}

POSITIONS = {
    "QB", "RB", "FB", "WR", "TE", "T", "OT", "G",
    "C", "OL", "DL", "DE", "DT", "NT", "EDGE",
    "LB", "ILB", "OLB", "CB", "DB", "S",
    "FS", "SS", "K", "P", "LS",
}


class InactiveParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.wrapper_depth = 0
        self.depth = 0
        self.tag = None
        self.team = None
        self.in_list = False
        self.buffer = []
        self.records = []
        self.seen = set()
        self.unsupported_positions = set()
        self.unrecognized_headings = set()
        self.recognized_team_headings = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if self.wrapper_depth:
            if tag == "div":
                self.depth += 1
        elif (
            tag == "div"
            and "story-part-rich-text-editor-wrapper"
            in attrs.get("class", "")
        ):
            self.wrapper_depth = 1
            self.team = None
            return

        if not self.wrapper_depth:
            return

        if tag == "h3":
            self.tag = "h3"
            self.buffer = []
        elif tag == "ul":
            self.in_list = True
        elif tag == "li" and self.in_list:
            self.tag = "li"
            self.buffer = []

    def handle_data(self, data):
        if self.tag:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if not self.wrapper_depth:
            return

        if tag == "h3" and self.tag == "h3":
            heading = unescape(
                "".join(self.buffer)
            ).strip().upper()

            heading_aliases = {
                "EAGLS": "EAGLES",
            }

            heading = heading_aliases.get(heading, heading)

            self.team = heading if heading in TEAMS else None

            if self.team:
                self.recognized_team_headings.add(self.team)

            if heading and heading not in TEAMS:
                self.unrecognized_headings.add(heading)

            self.tag = None

        elif tag == "li" and self.tag == "li":
            raw = unescape(
                "".join(self.buffer)
            ).strip()

            for line in raw.splitlines():
                line = line.strip()

                if not line:
                    continue

                match = re.match(
                    r"^([A-Za-z]+)[ \t]+(.+)$",
                    line,
                )

                if not match or not self.team:
                    continue

                position = match.group(1).upper()
                name = match.group(2).strip()

                if position not in POSITIONS:
                    self.unsupported_positions.add(position)
                    continue

                emergency = bool(
                    re.search(
                        r"emergency third QB",
                        name,
                        flags=re.IGNORECASE,
                    )
                )

                name = re.sub(
                    r"\s*\(emergency third QB\)",
                    "",
                    name,
                    flags=re.IGNORECASE,
                ).strip()

                key = (
                    self.team,
                    position,
                    name,
                )

                if key not in self.seen:
                    self.seen.add(key)
                    self.records.append({
                        "team": self.team,
                        "position": position,
                        "name": name,
                        "emergency_third_qb": emergency,
                        "source_url": SOURCE_URL,
                    })

            self.tag = None

        elif tag == "ul":
            self.in_list = False

        if tag == "div":
            self.depth -= 1

            if self.depth <= 0:
                self.wrapper_depth = 0
                self.depth = 0
                self.team = None
                self.in_list = False
                self.tag = None


def main():
    global SOURCE_URL

    cli = argparse.ArgumentParser()
    cli.add_argument(
        "--url",
        default=SOURCE_URL,
        help="NFL.com inactive report URL",
    )
    args = cli.parse_args()
    SOURCE_URL = args.url

    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(
        request, timeout=45
    ) as response:
        html = response.read().decode(
            "utf-8", errors="replace"
        )

    parser = InactiveParser()
    parser.feed(html)

    game_count_match = re.search(
        r"\bfor Sunday(?:'s|’s)\s+(\d+)\s+games\b",
        html,
        flags=re.IGNORECASE,
    )

    if not game_count_match:
        raise RuntimeError(
            "Could not determine expected Sunday game count"
        )

    expected_games = int(game_count_match.group(1))
    expected_teams = expected_games * 2
    actual_teams = len(parser.recognized_team_headings)

    print("Expected Sunday games:", expected_games)
    print("Expected team sections:", expected_teams)
    print("Actual team sections:", actual_teams)

    if actual_teams != expected_teams:
        raise RuntimeError(
            f"Incomplete team coverage: "
            f"expected {expected_teams}, found {actual_teams}"
        )

    records = parser.records
    teams = sorted({
        record["team"] for record in records
    })

    if len(records) < 10 or len(teams) < 2:
        raise RuntimeError(
            "Insufficient inactive records extracted"
        )

    missing_teams = (
        parser.recognized_team_headings - set(teams)
    )

    if missing_teams:
        raise RuntimeError(
            "Team headings without extracted players: "
            + ", ".join(sorted(missing_teams))
        )

    if parser.unrecognized_headings:
        raise RuntimeError(
            "Unrecognized team headings: "
            + ", ".join(sorted(parser.unrecognized_headings))
        )

    if parser.unsupported_positions:
        raise RuntimeError(
            "Unsupported position labels: "
            + ", ".join(sorted(parser.unsupported_positions))
        )
    result = {
        "source_url": SOURCE_URL,
        "retrieved_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "verification_status": "extracted_unverified",
        "expected_game_count": expected_games,
        "expected_team_count": expected_teams,
        "extracted_team_count": len(teams),
        "teams": teams,
        "player_count": len(records),
        "players": records,
        "schedule_verified": False,
        "kickoff_times_verified": False,
    }

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Extracted players:", len(records))
    print("Teams:", ", ".join(teams))
    print(
        "Unsupported position labels:",
        sorted(parser.unsupported_positions),
    )
    print(
        "Unrecognized team headings:",
        sorted(parser.unrecognized_headings),
    )
    print(
        "Recognized team headings:",
        len(parser.recognized_team_headings),
        sorted(parser.recognized_team_headings),
    )
    print(
        "Headings without extracted players:",
        sorted(parser.recognized_team_headings - set(teams)),
    )

    for record in records:
        if record["name"] in {
            "Quinshon Judkins",
            "Lamar Jackson",
        }:
            print("CHECK:", record)


if __name__ == "__main__":
    main()
