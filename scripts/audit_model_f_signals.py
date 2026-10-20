"""Historical expanding-window signal ablation. Does not change live projections."""
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("projection-model/2025-historical-ppr-dataset.csv")
OUT = Path("projection-model/validation/model-f-signal-ablation.csv")
BASE = ["opportunity_score", "production_score", "usage_score", "redzone_score", "model_confidence_score"]
FEATURES = {
    "QB": BASE + ["matchup_score"],
    "RB": BASE,
    "WR": BASE,
    "TE": BASE + ["matchup_score", "scoring_environment_score"],
}

def predict(train, test, columns):
    a = np.column_stack([np.ones(len(train)), train[columns].to_numpy(dtype=float)])
    b = np.column_stack([np.ones(len(test)), test[columns].to_numpy(dtype=float)])
    y = train["actual_ppr"].to_numpy(dtype=float)
    return b @ np.linalg.lstsq(a, y, rcond=None)[0]

def evaluate():
    df = pd.read_csv(DATA)
    df = df[df["position"].isin(FEATURES)].copy()
    for col in set(sum(FEATURES.values(), [])) | {"actual_ppr", "week"}:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    rows = []
    for position, baseline in FEATURES.items():
        group = df[df.position == position].copy()
        variants = {"Model F baseline": baseline}
        variants.update({"Without " + f: [c for c in baseline if c != f] for f in baseline})
        # Additional matchup experiment only where historical pregame signal exists.
        if position in ("RB", "WR") and "matchup_score" in group.columns:
            variants["With matchup_score"] = baseline + ["matchup_score"]
        for variant, cols in variants.items():
            eligible = group.dropna(subset=cols + ["actual_ppr", "week"])
            actuals, preds, week_count = [], [], 0
            for week in sorted(eligible.week.unique()):
                # Strict expanding window: never train on the test week or future weeks.
                train = eligible[eligible.week < week]
                test = eligible[eligible.week == week]
                if len(train) < max(40, len(cols) * 8) or len(test) < 5:
                    continue
                prediction = predict(train, test, cols)
                actuals.extend(test.actual_ppr.to_numpy(dtype=float))
                preds.extend(prediction)
                week_count += 1
            if not actuals:
                continue
            a, p = np.array(actuals), np.array(preds)
            rho = pd.Series(p).corr(pd.Series(a), method="spearman")
            rows.append({
                "position": position, "variant": variant, "features": "|".join(cols),
                "test_weeks": week_count, "test_rows": len(a),
                "mae": round(float(np.mean(np.abs(a-p))), 4),
                "rmse": round(float(np.sqrt(np.mean((a-p)**2))), 4),
                "spearman_pooled": round(float(rho), 4) if pd.notna(rho) else "",
                "method": "2025_expanding_window_week_split",
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print("Saved", OUT)
    print("NOTE: early weeks without sufficient past training are excluded; pooled Spearman is descriptive.")
if __name__ == "__main__":
    evaluate()
