"""Validate and apply week-scoped Data Daddy analyst adjustments.

This module does not mutate Model F inputs. Apply it to a copy of a completed
projection table. The original values remain available for later evaluation.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "data" / "analyst_adjustments.json"
CENT = Decimal("0.01")


def _delta(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a decimal number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{field} must be a decimal number") from None
    if not number.is_finite() or number != number.quantize(CENT):
        raise ValueError(f"{field} must be finite with at most 2 decimal places")
    return number


def load_adjustments(path=DEFAULT_CONFIG, *, season: int, week: int):
    """Return only validated adjustments matching the requested season/week."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("adjustments"), list):
        raise ValueError("Expected schema_version 1 and an adjustments array")
    selected, seen = [], set()
    for item in payload["adjustments"]:
        if not isinstance(item, dict):
            raise ValueError("Each adjustment must be an object")
        if type(item.get("season")) is not int or type(item.get("week")) is not int:
            raise ValueError("Adjustment season and week must be integers")
        if not (1 <= item["week"] <= 22):
            raise ValueError("Adjustment week must be between 1 and 22")
        pid = str(item.get("player_id", "")).strip()
        if not pid or pid == "REPLACE_WITH_CANONICAL_PLAYER_ID":
            raise ValueError("Each adjustment requires a canonical player_id")
        ai = _delta(item.get("ai_score_delta", "0"), "ai_score_delta")
        ppr = _delta(item.get("projected_ppr_delta", "0"), "projected_ppr_delta")
        if not ai and not ppr:
            raise ValueError(f"Player {pid} has no adjustment")
        for field in ("reason", "source", "author"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Player {pid} requires {field}")
        key = (item["season"], item["week"], pid)
        if key in seen:
            raise ValueError(f"Duplicate adjustment for {key}")
        seen.add(key)
        if (item["season"], item["week"]) == (season, week):
            selected.append({**item, "player_id": pid, "ai_score_delta": ai,
                             "projected_ppr_delta": ppr})
    return selected


def apply_adjustments(frame: pd.DataFrame, *, season: int, week: int,
                      config_path=DEFAULT_CONFIG):
    """Return (adjusted_dataframe, audit_dataframe); never modify input."""
    required = {"player_id", "position", "model_score", "projected_ppr"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing projection columns: {sorted(required - set(frame.columns))}")
    result = frame.copy(deep=True)
    result["original_model_score"] = result["model_score"].copy()
    result["original_projected_ppr"] = result["projected_ppr"].copy()
    audit = []
    for adj in load_adjustments(config_path, season=season, week=week):
        mask = result["player_id"].astype(str).eq(adj["player_id"])
        if mask.sum() != 1:
            raise ValueError(f"Expected exactly one row for player_id {adj['player_id']}; found {mask.sum()}")
        idx = result.index[mask][0]
        original_ai = Decimal(str(result.at[idx, "model_score"]))
        original_ppr = Decimal(str(result.at[idx, "projected_ppr"]))
        adjusted_ai = (original_ai + adj["ai_score_delta"]).quantize(CENT)
        adjusted_ppr = (original_ppr + adj["projected_ppr_delta"]).quantize(CENT)
        if not Decimal("0") <= adjusted_ai <= Decimal("100") or adjusted_ppr < 0:
            raise ValueError(f"Adjusted values out of range for {adj['player_id']}")
        result.at[idx, "model_score"] = float(adjusted_ai)
        result.at[idx, "projected_ppr"] = float(adjusted_ppr)
        audit.append({"season": season, "week": week, "player_id": adj["player_id"],
                      "player_name": result.at[idx, "player_name"] if "player_name" in result else "",
                      "original_ai_score": str(original_ai), "ai_delta": str(adj["ai_score_delta"]),
                      "adjusted_ai_score": str(adjusted_ai),
                      "original_ppr": str(original_ppr), "ppr_delta": str(adj["projected_ppr_delta"]),
                      "adjusted_ppr": str(adjusted_ppr),
                      "reason": adj["reason"], "source": adj["source"], "author": adj["author"]})
    if audit:
        adjusted_ids = {entry["player_id"] for entry in audit}
        affected_positions = set(
            result.loc[result["player_id"].astype(str).isin(adjusted_ids), "position"]
        )
        for position, group in result.groupby("position"):
            if position not in affected_positions:
                continue
            order_ai = group.sort_values(["model_score", "player_id"], ascending=[False, True]).index
            order_ppr = group.sort_values(["projected_ppr", "player_id"], ascending=[False, True]).index
            result.loc[order_ai, "position_rank"] = list(range(1, len(order_ai) + 1))
            result.loc[order_ppr, "projected_position_rank"] = list(range(1, len(order_ppr) + 1))
    return result, pd.DataFrame(audit)
