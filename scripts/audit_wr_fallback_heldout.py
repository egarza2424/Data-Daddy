"""Review-only historical WR missing-evidence fallback audit. No production writes."""
from pathlib import Path
import numpy as np
import pandas as pd

SOURCE = Path("projection-model/2025-historical-ppr-dataset.csv")
FEATURES = ["opportunity_score", "production_score", "usage_score",
            "redzone_score", "model_confidence_score"]
FALLBACK = {"opportunity_score": 50, "production_score": 0,
            "usage_score": 20, "redzone_score": 50,
            "model_confidence_score": 50}
OUT = Path("projection-model/validation/2025-wr-fallback-audit.csv")

def main():
    data = pd.read_csv(SOURCE)
    wr = data.loc[data["position"].astype(str).str.upper().eq("WR")].copy()
    required = FEATURES + ["actual_ppr"]
    wr[required] = wr[required].apply(pd.to_numeric, errors="coerce")
    wr = wr.dropna(subset=required)
    if len(wr) < 30:
        raise RuntimeError("Insufficient historical WR observations")
    mask = pd.Series(True, index=wr.index)
    for feature, value in FALLBACK.items():
        mask &= wr[feature].eq(value)
    if not mask.any():
        print("No exact historical fallback WR profiles; cannot claim validated improvement.")
        print("Historical WR rows:", len(wr))
        return
    x = np.column_stack([np.ones(len(wr)), wr[FEATURES].to_numpy(float)])
    y = wr["actual_ppr"].to_numpy(float)
    results = []
    # Hold out each row in five deterministic folds; no in-sample evaluation.
    folds = np.arange(len(wr)) % 5
    for fold in range(5):
        train, test = folds != fold, folds == fold
        beta = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
        baseline = np.maximum(0, x[test] @ beta)
        actual = y[test]
        flagged = mask.to_numpy()[test]
        for multiplier in [1.0, 0.75, 0.5, 0.25, 0.0]:
            predicted = baseline.copy()
            predicted[flagged] *= multiplier
            for group, selected in [("all", np.ones(len(actual), bool)),
                                    ("fallback", flagged),
                                    ("non_fallback", ~flagged)]:
                if not selected.any():
                    continue
                err = predicted[selected] - actual[selected]
                results.append(dict(fold=fold, multiplier=multiplier, group=group,
                                    n=int(selected.sum()), absolute_error=float(np.abs(err).sum()),
                                    signed_error=float(err.sum()), overprojected=int((err > 0).sum())))
    output = pd.DataFrame(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUT, index=False)
    print("Historical WR rows:", len(wr), "exact fallback rows:", int(mask.sum()))
    for (multiplier, group), sub in output.groupby(["multiplier", "group"]):
        n = sub["n"].sum()
        print(f"multiplier={multiplier:.2f} group={group} n={n} MAE={sub['absolute_error'].sum()/n:.4f} bias={sub['signed_error'].sum()/n:.4f} overprojection={sub['overprojected'].sum()/n:.1%}")
    print("Saved review-only:", OUT)

if __name__ == "__main__":
    main()
