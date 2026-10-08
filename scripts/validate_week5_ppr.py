
#!/usr/bin/env python3
"""Validate frozen Week 5 PPR predictions against postgame actual PPR.

Usage:
  python scripts/validate_week5_ppr.py \
    --predictions projection-model/2026-week5-ppr-projections.csv \
    --actuals projection-model/2026-week5-actual-ppr.csv \
    --output-dir projection-model/validation/week5

Actuals CSV required columns: player_id, actual_ppr
Optional: player_name, position. Only players present in both files are scored.
The actuals file must contain all players with a game, including zero-point games.
"""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def ranks(values):
    """Average ranks for ties, with highest value ranked first."""
    indices = sorted(range(len(values)), key=lambda i: -values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(indices):
        j = i + 1
        while j < len(indices) and values[indices[j]] == values[indices[i]]:
            j += 1
        rank = (i + 1 + j) / 2
        for k in indices[i:j]:
            result[k] = rank
        i = j
    return result


def spearman(pred, actual):
    if len(pred) < 2:
        return None
    x, y = ranks(pred), ranks(actual)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    numerator = sum((a-mx)*(b-my) for a,b in zip(x,y))
    denominator = math.sqrt(sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))
    return numerator / denominator if denominator else None


def fmt(x):
    return '' if x is None else round(x, 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--actuals', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    predictions = read_csv(args.predictions)
    actuals = read_csv(args.actuals)
    if not predictions or not actuals:
        raise SystemExit('Both input CSVs must contain data rows.')
    for label, rows, required in [
        ('Predictions', predictions, {'player_id','player_name','position','projected_ppr','snapshot_week'}),
        ('Actuals', actuals, {'player_id','actual_ppr'}),
    ]:
        missing = required - rows[0].keys()
        if missing:
            raise SystemExit(f'{label} missing columns: {sorted(missing)}')

    prediction_ids = [row['player_id'].strip() for row in predictions]
    actual_ids = [row['player_id'].strip() for row in actuals]
    if len(prediction_ids) != len(set(prediction_ids)) or len(actual_ids) != len(set(actual_ids)):
        raise SystemExit('Duplicate player_id detected in predictions or actuals; fix before validation.')
    if any(row['snapshot_week'].strip() != '5' for row in predictions):
        raise SystemExit('Predictions include a week other than Week 5.')
    actual_by_id = {r['player_id'].strip(): r for r in actuals}
    compared, unmatched = [], []
    for p in predictions:
        player_id = p['player_id'].strip()
        a = actual_by_id.get(player_id)
        if a is None or a['actual_ppr'].strip() == '':
            unmatched.append({'player_id': player_id, 'player_name': p['player_name'], 'position': p['position'], 'reason': 'Missing actual PPR'})
            continue
        if a.get('position') and a['position'].strip().upper() != p['position'].strip().upper():
            raise SystemExit(f'Position mismatch for player_id {player_id}')
        projected, actual = float(p['projected_ppr']), float(a['actual_ppr'])
        if not math.isfinite(projected) or not math.isfinite(actual):
            raise SystemExit(f'Non-finite PPR for player_id {player_id}')
        compared.append({
            'player_id': player_id, 'player_name': p['player_name'], 'position': p['position'],
            'team': p.get('team',''), 'projected_ppr': projected, 'actual_ppr': actual,
            'error': round(projected - actual, 4), 'absolute_error': round(abs(projected - actual), 4),
        })

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for row in compared:
        grouped[row['position']].append(row)
    grouped['ALL'] = compared
    summary = []
    for pos in ['ALL','QB','RB','WR','TE']:
        rows = grouped[pos]
        if not rows:
            continue
        n = len(rows)
        pred = [r['projected_ppr'] for r in rows]
        actual = [r['actual_ppr'] for r in rows]
        summary.append({
            'position': pos, 'matched_players': n,
            'mae': fmt(sum(r['absolute_error'] for r in rows) / n),
            'rmse': fmt(math.sqrt(sum(r['error']**2 for r in rows) / n)),
            'bias_projected_minus_actual': fmt(sum(r['error'] for r in rows) / n),
            'spearman_rank_correlation': fmt(spearman(pred, actual)),
        })
        if pos != 'ALL':
            pr, ar = ranks(pred), ranks(actual)
            for r, p_rank, a_rank in zip(rows, pr, ar):
                r['projected_rank_matched_pool'] = p_rank
                r['actual_rank_matched_pool'] = a_rank
                r['rank_difference'] = p_rank - a_rank

    comparison_fields = ['player_id','player_name','position','team','projected_ppr','actual_ppr',
                         'error','absolute_error','projected_rank_matched_pool',
                         'actual_rank_matched_pool','rank_difference']
    write_csv(output_dir/'week5-player-comparison.csv',
              sorted(compared, key=lambda r: -r['absolute_error']), comparison_fields)
    write_csv(output_dir/'week5-position-summary.csv', summary, list(summary[0]))
    write_csv(output_dir/'week5-unmatched-projections.csv', unmatched,
              ['player_id','player_name','position','reason'])
    print(f'Predictions: {len(predictions)} | Actual rows: {len(actuals)} | Matched: {len(compared)} | Unmatched predictions: {len(unmatched)}')
    for row in summary:
        print(f"{row['position']:>3} n={row['matched_players']:>3} MAE={row['mae']} RMSE={row['rmse']} Bias={row['bias_projected_minus_actual']} Spearman={row['spearman_rank_correlation']}")
    if unmatched:
        print('WARNING: Coverage incomplete. Do not treat these metrics as full-week accuracy.')
    print(f'Wrote validation files to {output_dir}')


if __name__ == '__main__':
    main()
