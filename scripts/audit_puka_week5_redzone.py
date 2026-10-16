
import argparse
import csv
import gzip

PUKA_ID = "00-0039075"
SEASON = 2026
WEEK = 5

ZONES = {
    "20-11": {"carries": 0, "targets": 0},
    "10-6": {"carries": 0, "targets": 0},
    "5-1": {"carries": 0, "targets": 0},
}


def get_zone(yardline):
    if 11 <= yardline <= 20:
        return "20-11"
    if 6 <= yardline <= 10:
        return "10-6"
    if 1 <= yardline <= 5:
        return "5-1"
    return None


def main(path):
    with gzip.open(path, "rt", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for play in reader:
            try:
                season = int(float(play["season"]))
                week = int(float(play["week"]))
                yardline = float(play["yardline_100"])
            except (ValueError, TypeError):
                continue

            if season != SEASON or week != WEEK:
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
                ZONES[zone]["carries"] += 1

            if (
                play["pass_attempt"] == "1"
                and play["receiver_player_id"] == PUKA_ID
            ):
                ZONES[zone]["targets"] += 1

    print("PUKA NACUA — WEEK 5 RED-ZONE AUDIT")
    print("----------------------------------")

    weighted = 0

    for zone, weight in [
        ("20-11", 1),
        ("10-6", 2),
        ("5-1", 3),
    ]:
        carries = ZONES[zone]["carries"]
        targets = ZONES[zone]["targets"]

        weighted += (carries + targets) * weight

        print(
            f"{zone}: carries={carries}, "
            f"targets={targets}"
        )

    print("----------------------------------")
    print(f"Weighted opportunities: {weighted}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbp", required=True)
    args = parser.parse_args()

    main(args.pbp)
