"""Isolated, pregame-only RB inside-the-five challenger validation (2023-2025)."""
import argparse
import csv
import gzip
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ALIASES = {"LAR": "LA", "JAX": "JAC", "WAS": "WSH"}
BASE = ["opportunity_score", "production_score", "usage_score",
        "redzone_score", "model_confidence_score"]


def team_key(value):
    name = str(value).strip().upper()
    return ALIASES.get(name, name)


def extract_pbp(path, season):
    """Return player/team rushing-attempt counts by week and field position."""
    player = defaultdict(lambda: [0, 0])
    team = defaultdict(lambda: [0, 0])
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for play in csv.DictReader(handle):
            if play.get("season_type") != "REG" or play.get("rush_attempt") != "1":
                continue
            try:
                if int(float(play.get("season") or 0)) != season:
                    continue
                week = int(float(play.get("week") or 0))
                yard = float(play.get("yardline_100") or "nan")
            except (TypeError, ValueError):
                continue
            if not (1 <= week <= 18 and np.isfinite(yard) and 0 <= yard <= 20):
                continue
            pid = str(play.get("rusher_player_id") or "").strip()
            team_name = team_key(play.get("posteam"))
            if not pid or team_name in ("", "NAN", "NONE"):
                continue
            player[(pid, week)][0] += 1
            team[(team_name, week)][0] += 1
            if yard <= 5:
                player[(pid, week)][1] += 1
                team[(team_name, week)][1] += 1
    return player, team


def add_features(frame, player, team):
    rows = []
    for row in frame.itertuples(index=False):
        week = int(row.week)
        # Strictly prior three calendar weeks: byes contribute zero, never future data.
        prior = range(max(1, week - 3), week)
        p_rz = sum(player[(row.player_id, w)][0] for w in prior)
        p_five = sum(player[(row.player_id, w)][1] for w in prior)
        t_five = sum(team[(row.team_key, w)][1] for w in prior)
        rows.append((p_rz, p_five, t_five,
                     100 * p_five / t_five if t_five else 0.0,
                     int(t_five > 0)))
    cols = ["prior_rz_carries", "prior_inside5_carries", "prior_team_inside5_carries",
            "inside5_share", "team_inside5_opportunity_observed"]
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(rows, columns=cols)], axis=1)


def fit_predict(train, test, columns):
    x_train = np.c_[np.ones(len(train)), train[columns].to_numpy(dtype=float)]
    x_test = np.c_[np.ones(len(test)), test[columns].to_numpy(dtype=float)]
    coef = np.linalg.lstsq(x_train, train.actual_ppr.to_numpy(dtype=float), rcond=None)[0]
    return x_test @ coef


def metrics(y, prediction):
    corr = spearmanr(y, prediction).statistic
    return {"MAE": round(float(np.mean(np.abs(y - prediction))), 4),
            "RMSE": round(float(np.sqrt(np.mean((y - prediction) ** 2))), 4),
            "Spearman": round(float(corr), 4) if np.isfinite(corr) else None}


def validate(season, dataset, pbp, output):
    df = pd.read_csv(dataset, low_memory=False)
    df = df[df.position.eq("RB")].copy()
    df["week"] = pd.to_numeric(df.week, errors="coerce")
    df = df[df.week.between(4, 18)].copy()
    df["player_id"] = df.player_id.astype(str).str.strip()
    df["team_key"] = df.team.map(team_key)
    for field in BASE + ["actual_ppr"]:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    df = df.dropna(subset=BASE + ["actual_ppr", "week"])
    player, team = extract_pbp(pbp, season)
    df = add_features(df, player, team)
    train = df[df.week.between(4, 12)].copy()
    test = df[df.week.between(13, 18)].copy()
    if len(train) < 100 or len(test) < 100:
        raise ValueError(f"Insufficient data in {season}: train={len(train)}, test={len(test)}")
    # Nested challenger: retain all baseline features, add goal-line opportunity.
    test["baseline_prediction"] = fit_predict(train, test, BASE)
    test["challenger_prediction"] = fit_predict(train, test, BASE + ["inside5_share"])
    y = test.actual_ppr.to_numpy(dtype=float)
    summary = []
    for label, column in [("Model F historical baseline", "baseline_prediction"),
                          ("Model F + prior 3-week inside-5 carry share", "challenger_prediction")]:
        summary.append({"season": season, "model": label, **metrics(y, test[column].to_numpy(dtype=float)),
                        "train_rows": len(train), "test_rows": len(test),
                        "test_rows_team_inside5_observed": int(test.team_inside5_opportunity_observed.sum()),
                        "test_rows_player_inside5_positive": int((test.prior_inside5_carries > 0).sum())})
    output.mkdir(parents=True, exist_ok=True)
    detail_path = output / f"{season}-rb-inside5-backtest.csv"
    summary_path = output / f"{season}-rb-inside5-summary.csv"
    test[["season", "week", "player_id", "player_name", "team", "actual_ppr",
          "redzone_score", "prior_rz_carries", "prior_inside5_carries",
          "prior_team_inside5_carries", "inside5_share", "team_inside5_opportunity_observed",
          "baseline_prediction", "challenger_prediction"]].to_csv(detail_path, index=False)
    pd.DataFrame(summary).to_csv(summary_path, index=False)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--output", type=Path, default=Path("projection-model/validation"))
    args = parser.parse_args()
    all_results = []
    for season in args.seasons:
        dataset = Path(f"projection-model/{season}-historical-ppr-dataset.csv")
        pbp = Path(f"historical-data/play_by_play_{season}.csv.gz")
        for path in (dataset, pbp):
            if not path.is_file():
                raise FileNotFoundError(f"Missing {path}; run the historical-data workflow first")
        all_results.extend(validate(season, dataset, pbp, args.output))
    pd.DataFrame(all_results).to_csv(args.output / "2023-2025-rb-inside5-summary.csv", index=False)


if __name__ == "__main__":
    main()
