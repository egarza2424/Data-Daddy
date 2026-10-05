import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SEASON = 2026
WEEK = 4
SCORING = "PPR"

POSITIONS = ("QB", "RB", "WR", "TE")

API_BASE_URL = (
    f"https://api.fantasypros.com/public/v2/json/nfl/"
    f"{SEASON}/consensus-rankings"
)

OUTPUT_DIR = Path("projection-model")
OUTPUT_FILE = OUTPUT_DIR / (
    f"{SEASON}-week{WEEK}-market-consensus.csv"
)

OUTPUT_COLUMNS = [
    "season",
    "week",
    "player_id",
    "player_name",
    "position",
    "team",
    "ecr_rank",
    "ecr_position_rank",
    "ecr_best_rank",
    "ecr_worst_rank",
    "ecr_std_dev",
    "experts_count",
    "ecr_updated",
    "snapshot_timestamp",
]


def get_api_key():
    api_key = os.environ.get(
        "FANTASYPROS_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "FANTASYPROS_API_KEY is not set."
        )

    return api_key


def fetch_position_rankings(
    api_key,
    position,
):
    query = urllib.parse.urlencode(
        {
            "week": WEEK,
            "position": position,
            "scoring": SCORING,
        }
    )

    url = f"{API_BASE_URL}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": (
                "Fantasy-AI-Player-Lab/1.0"
            ),
        },
        method="GET",
    )

    print(
        f"Fetching Week {WEEK} "
        f"{position} {SCORING} ECR..."
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            status = response.status
            body = response.read().decode(
                "utf-8"
            )

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"FantasyPros returned HTTP "
            f"{error.code} for {position}: "
            f"{error_body[:500]}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not reach FantasyPros "
            f"for {position}: {error}"
        ) from error

    if status != 200:
        raise RuntimeError(
            f"Unexpected FantasyPros status "
            f"{status} for {position}."
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"FantasyPros returned invalid "
            f"JSON for {position}."
        ) from error

    return payload


def find_rankings_list(payload):
    """
    FantasyPros response structures can
    include rankings under different nested
    keys depending on endpoint/version.

    Search only for a list containing ranking
    records rather than assuming one path.
    """

    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    preferred_keys = (
        "players",
        "rankings",
        "results",
    )

    for key in preferred_keys:
        value = payload.get(key)

        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
        ):
            return value

    for value in payload.values():
        if isinstance(value, dict):
            found = find_rankings_list(value)

            if found:
                return found

    return []


def first_value(record, keys):
    for key in keys:
        value = record.get(key)

        if value is not None and value != "":
            return value

    return ""


def normalize_rank(value):
    if value is None or value == "":
        return ""

    text = str(value).strip()

    if not text:
        return ""

    try:
        return int(float(text))
    except (TypeError, ValueError):
        return text


def normalize_float(value):
    if value is None or value == "":
        return ""

    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return value


def build_rows(
    rankings,
    requested_position,
    snapshot_timestamp,
):
    rows = []

    for record in rankings:
        if not isinstance(record, dict):
            continue

        player_name = first_value(
            record,
            (
                "player_name",
                "name",
                "player",
            ),
        )

        if isinstance(player_name, dict):
            player_name = first_value(
                player_name,
                (
                    "player_name",
                    "name",
                    "full_name",
                ),
            )

        position = str(
            first_value(
                record,
                (
                    "position",
                    "player_position",
                ),
            )
            or requested_position
        ).upper()

        if position != requested_position:
            continue

        ecr_rank = normalize_rank(
            first_value(
                record,
                (
                    "rank_ecr",
                    "ecr",
                    "rank",
                ),
            )
        )

        position_rank = first_value(
            record,
            (
                "pos_rank",
                "position_rank",
                "rank_position",
            ),
        )

        if isinstance(position_rank, str):
            digits = "".join(
                character
                for character in position_rank
                if character.isdigit()
            )

            if digits:
                position_rank = digits

        position_rank = normalize_rank(
            position_rank
        )

        if not player_name:
            continue

        if ecr_rank == "":
            continue

        if position_rank == "":
            continue

        row = {
            "season": SEASON,
            "week": WEEK,
            "player_id": first_value(
                record,
                (
                    "player_id",
                    "id",
                    "sportsdata_id",
                ),
            ),
            "player_name": player_name,
            "position": position,
            "team": first_value(
                record,
                (
                    "team",
                    "player_team_id",
                    "team_id",
                ),
            ),
            "ecr_rank": ecr_rank,
            "ecr_position_rank":
                position_rank,
            "ecr_best_rank": normalize_rank(
                first_value(
                    record,
                    (
                        "rank_min",
                        "best_rank",
                    ),
                )
            ),
            "ecr_worst_rank": normalize_rank(
                first_value(
                    record,
                    (
                        "rank_max",
                        "worst_rank",
                    ),
                )
            ),
            "ecr_std_dev": normalize_float(
                first_value(
                    record,
                    (
                        "rank_std",
                        "std_dev",
                    ),
                )
            ),
            "experts_count": normalize_rank(
                first_value(
                    record,
                    (
                        "experts_available",
                        "experts_count",
                        "num_experts",
                    ),
                )
            ),
            "ecr_updated": first_value(
                record,
                (
                    "rank_ecr_updated",
                    "last_updated",
                    "updated",
                ),
            ),
            "snapshot_timestamp":
                snapshot_timestamp,
        }

        rows.append(row)

    return rows


def validate_rows(rows):
    if not rows:
        raise RuntimeError(
            "FantasyPros returned zero usable "
            "consensus ranking rows."
        )

    counts = {
        position: 0
        for position in POSITIONS
    }

    for row in rows:
        position = row["position"]

        if position in counts:
            counts[position] += 1

    print()
    print("Consensus row counts:")

    for position in POSITIONS:
        print(
            f"  {position}: "
            f"{counts[position]}"
        )

    missing_positions = [
        position
        for position, count
        in counts.items()
        if count == 0
    ]

    if missing_positions:
        raise RuntimeError(
            "No usable rankings returned for: "
            + ", ".join(missing_positions)
        )

    seen = set()

    for row in rows:
        key = (
            str(row["player_id"]).strip()
            or (
                str(row["player_name"])
                .strip()
                .lower(),
                row["position"],
            )
        )

        if key in seen:
            raise RuntimeError(
                "Duplicate consensus player "
                f"detected: "
                f"{row['player_name']} "
                f"({row['position']})"
            )

        seen.add(key)


def write_csv(rows):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_FILE.with_suffix(
        ".csv.tmp"
    )

    with temporary_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(rows)

    temporary_file.replace(OUTPUT_FILE)


def main():
    api_key = get_api_key()

    snapshot_timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )

    all_rows = []

    for position in POSITIONS:
        payload = fetch_position_rankings(
            api_key,
            position,
        )

        rankings = find_rankings_list(
            payload
        )

        print(
            f"  Raw ranking records found: "
            f"{len(rankings)}"
        )

        rows = build_rows(
            rankings,
            position,
            snapshot_timestamp,
        )

        print(
            f"  Usable {position} rows: "
            f"{len(rows)}"
        )

        all_rows.extend(rows)

    validate_rows(all_rows)

    all_rows.sort(
        key=lambda row: (
            POSITIONS.index(
                row["position"]
            ),
            int(row["ecr_position_rank"])
            if str(
                row["ecr_position_rank"]
            ).isdigit()
            else 9999,
            str(row["player_name"]),
        )
    )

    write_csv(all_rows)

    print()
    print(
        "FantasyPros market consensus "
        "snapshot complete."
    )
    print(
        f"Rows written: {len(all_rows)}"
    )
    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
