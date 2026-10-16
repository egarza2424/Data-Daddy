
import argparse
import csv
import gzip

PUKA_ID = "00-0039075"
SEASON = 2026
WEEKS = (1, 4, 5)

ZONE_WEIGHTS = {
    "20-11": 1,
    "10-6": 2,
    "5-1": 3,
}


def get_zone(yardline):
    if 11 <= yardline <= 20:
        return "20-11"
    if 6 <= yardline <= 10:
        return "10-6"
    if 1 <= yardline <= 5:
        return "5-1"
    return None


def empty_counts():
    return {
        zone: {"carries": 0, "targets": 0}
        for zone in ZONE_WEIGHTS
    }


def main(path):
    results = {
        week: empty_counts()
        for week in WEEKS
    }

    with gzip.open(path, "rt", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for play in reader:
            try:
                season = int(float(play["season"]))
                week = int(float(play["week"]))
                yardline = float(play["yardline_100"])
            except (ValueError, TypeError):
                continue

            if season != SEASON or week not in WEEKS:
                continue

            if play["season_type"] != "REG":
                continue

            zone = get_zone(yardline)
            if zone is None:
                continue

            if (
                play["rush_attempt"] == "1"
                and play["rusher_player_id"] == PUKA_ID
            ):
                results[week][zone]["carries"] += 1

            if (
                play["pass_attempt"] == "1"
                and play["receiver_player_id"] == PUKA_ID
            ):
                results[week][zone]["targets"] += 1

    print("PUKA NACUA — WEEKS 1, 4, 5 RED-ZONE AUDIT")
    print("=" * 48)

    combined = empty_counts()
    grand_total = 0

    for week in WEEKS:
        print(f"\nWEEK {week}")
        weekly_total = 0

        for zone, weight in ZONE_WEIGHTS.items():
            carries = results[week][zone]["carries"]
            targets = results[week][zone]["targets"]

            combined[zone]["carries"] += carries
            combined[zone]["targets"] += targets

            weighted = (carries + targets) * weight
            weekly_total += weighted

            print(
                f"{zone}: carries={carries}, "
                f"targets={targets}, weighted={weighted}"
            )

        grand_total += weekly_total
        print(f"Week {week} weighted total: {weekly_total}")

    print("\nCOMBINED THREE-GAME TOTALS")

    for zone in ZONE_WEIGHTS:
        counts = combined[zone]
        print(
            f"{zone}: carries={counts['carries']}, "
            f"targets={counts['targets']}"
        )

    print(f"\nTotal weighted opportunities: {grand_total}")
    print(f"Weighted opportunities/game: {grand_total / len(WEEKS):.4f}")

    expected = 13
    print(f"Expected frozen-feed total: {expected}")
    print(f"Audit result: {'PASS' if grand_total == expected else 'FAIL'}")

    if grand_total != expected:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbp", required=True)
    args = parser.parse_args()

    main(args.pbp)
