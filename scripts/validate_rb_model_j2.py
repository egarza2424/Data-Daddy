"""Walk-forward RB comparison: production baseline F and experimental I, J1, J2.

J2 adds pregame workload trend features to J1 season-to-date efficiency.
Validation-only outputs; does not modify production predictions.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path('projection-model/validation')
BASELINE = [
    'opportunity_score', 'production_score', 'usage_score',
    'redzone_score', 'model_confidence_score',
]
REQUIRED = BASELINE + [
    'season', 'week', 'player_id', 'player_name', 'position', 'actual_ppr',
    'rb_prior_games', 'rb_carries_pg', 'rb_targets_pg', 'rb_receptions_pg',
    'rb_rush_yards_pg', 'rb_receiving_yards_pg', 'rb_redzone_carries_pg',
    'rb_redzone_targets_pg', 'implied_team_total', 'rb_season_games',
    'rb_season_carries', 'rb_season_targets', 'rb_season_receptions',
    'rb_season_rush_yards', 'rb_season_receiving_yards',
]
MODELS = (
    'F_position_specific', 'I_RB_component',
    'J1_RB_season_efficiency', 'J2_RB_role_stability',
)


def ols(train_x, train_y, test_x):
    x = np.column_stack([np.ones(len(train_x)), np.asarray(train_x, float)])
    z = np.column_stack([np.ones(len(test_x)), np.asarray(test_x, float)])
    coefficients = np.linalg.lstsq(x, np.asarray(train_y, float), rcond=None)[0]
    return np.maximum(0, z @ coefficients)


def priors(train):
    n = train['rb_prior_games'].to_numpy(float)
    carries = train['rb_carries_pg'].to_numpy(float) * n
    targets = train['rb_targets_pg'].to_numpy(float) * n
    catches = train['rb_receptions_pg'].to_numpy(float) * n
    rush = train['rb_rush_yards_pg'].to_numpy(float) * n
    receiving = train['rb_receiving_yards_pg'].to_numpy(float) * n
    return (
        rush.sum() / max(carries.sum(), 1),
        np.clip(catches.sum() / max(targets.sum(), 1), 0, 1),
        receiving.sum() / max(catches.sum(), 1),
    )


def role_trends(frame):
    """Compare recent 3-game workload with prior-season games, excluding overlap.

    All inputs were constructed using games strictly before the prediction week.
    For <=3 historical games, no non-overlapping baseline exists: trend = 0.
    """
    season_games = frame['rb_season_games'].to_numpy(float)
    recent_games = frame['rb_prior_games'].to_numpy(float)
    earlier_games = np.maximum(season_games - recent_games, 0)
    valid = earlier_games > 0
    result = []
    for season_total, recent_average in (
        ('rb_season_carries', 'rb_carries_pg'),
        ('rb_season_targets', 'rb_targets_pg'),
    ):
        recent_pg = frame[recent_average].to_numpy(float)
        total = frame[season_total].to_numpy(float)
        earlier_total = np.maximum(total - recent_pg * recent_games, 0)
        earlier_pg = np.divide(
            earlier_total, earlier_games,
            out=np.zeros_like(earlier_total), where=valid,
        )
        # Signed opportunity difference, shrunk for short earlier histories.
        difference = recent_pg - earlier_pg
        reliability = earlier_games / (earlier_games + 3.0)
        result.append(np.where(valid, difference * reliability, 0.0))
    return np.column_stack(result)


def features(frame, prior, model):
    carries = frame['rb_carries_pg'].to_numpy(float)
    targets = frame['rb_targets_pg'].to_numpy(float)
    receptions = frame['rb_receptions_pg'].to_numpy(float)
    rush_yards = frame['rb_rush_yards_pg'].to_numpy(float)
    rec_yards = frame['rb_receiving_yards_pg'].to_numpy(float)
    n = frame['rb_prior_games'].to_numpy(float)
    if model == 'I_RB_component':
        rush_attempts = np.maximum(0, carries * n)
        target_attempts = np.maximum(0, targets * n)
        catch_count = np.maximum(0, receptions * n)
        ypc = (rush_yards * n + 40 * prior[0]) / (rush_attempts + 40)
        catch_rate = (catch_count + 25 * prior[1]) / (target_attempts + 25)
        ypr = (rec_yards * n + 20 * prior[2]) / (catch_count + 20)
    else:
        rush_attempts = frame['rb_season_carries'].to_numpy(float)
        target_attempts = frame['rb_season_targets'].to_numpy(float)
        catch_count = frame['rb_season_receptions'].to_numpy(float)
        ypc = (frame['rb_season_rush_yards'].to_numpy(float) + 40 * prior[0]) / (rush_attempts + 40)
        catch_rate = (frame['rb_season_receptions'].to_numpy(float) + 25 * prior[1]) / (target_attempts + 25)
        ypr = (frame['rb_season_receiving_yards'].to_numpy(float) + 20 * prior[2]) / (catch_count + 20)
    rush_points = carries * ypc * 0.1
    receiving_points = targets * catch_rate * (1 + ypr * 0.1)
    base = np.column_stack([
        rush_points, receiving_points,
        frame['rb_redzone_carries_pg'].to_numpy(float),
        frame['rb_redzone_targets_pg'].to_numpy(float),
        frame['implied_team_total'].to_numpy(float),
    ])
    if model == 'J2_RB_role_stability':
        return np.column_stack([base, role_trends(frame)])
    return base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', type=int, required=True, choices=[2024, 2025])
    args = parser.parse_args()
    path = Path(f'projection-model/{args.season}-historical-ppr-dataset.csv')
    data = pd.read_csv(path)
    missing = sorted(set(REQUIRED) - set(data.columns))
    if missing:
        raise ValueError(f'Missing historical columns: {missing}')
    if not data['season'].eq(args.season).all():
        raise ValueError('Unexpected season in historical dataset')
    rb = data.loc[data['position'].eq('RB')].copy()
    if rb.empty or rb[REQUIRED].isna().any().any():
        raise ValueError('Empty RB dataset or missing required values')
    if rb.duplicated(['season', 'week', 'player_id']).any():
        raise ValueError('Duplicate RB player-week rows')
    if (rb['rb_prior_games'] > rb['rb_season_games']).any():
        raise ValueError('Recent game count exceeds season-to-date game count')
    records = []
    for week in sorted(rb['week'].unique()):
        if week < 7:
            continue
        train = rb.loc[rb['week'] < week]
        test = rb.loc[rb['week'] == week]
        if train.empty or test.empty:
            continue
        prior = priors(train)
        actual_train = train['actual_ppr'].to_numpy(float)
        estimates = {'F_position_specific': ols(train[BASELINE], actual_train, test[BASELINE])}
        for model in MODELS[1:]:
            estimates[model] = ols(
                features(train, prior, model), actual_train,
                features(test, prior, model),
            )
        for model, values in estimates.items():
            part = test[['season', 'week', 'player_id', 'player_name', 'actual_ppr']].copy()
            part['model'] = model
            part['projected_ppr'] = values
            part['training_through_week'] = week - 1
            part['training_rows'] = len(train)
            records.append(part)
    if not records:
        raise ValueError('No walk-forward predictions produced')
    predictions = pd.concat(records, ignore_index=True)
    predictions['actual_rank'] = predictions.groupby(['model', 'week'])['actual_ppr'].rank(
        method='min', ascending=False,
    )
    predictions['projected_rank'] = predictions.groupby(['model', 'week'])['projected_ppr'].rank(
        method='min', ascending=False,
    )
    predictions['absolute_rank_error'] = (
        predictions['actual_rank'] - predictions['projected_rank']
    ).abs()
    tiers = []
    for (model, week), group in predictions.groupby(['model', 'week']):
        for cutoff in (12, 24):
            actual = set(group.nsmallest(cutoff, 'actual_rank')['player_id'])
            predicted = set(group.nsmallest(cutoff, 'projected_rank')['player_id'])
            selected = group[group['player_id'].isin(predicted)]
            tiers.append({
                'model': model, 'week': week, 'tier': f'Top {cutoff}',
                'correct_picks': len(actual & predicted), 'total_picks': len(predicted),
                'hit_rate': round(len(actual & predicted) / len(predicted), 4),
                'mean_rank_error': round(selected['absolute_rank_error'].mean(), 4),
            })
    tier_weekly = pd.DataFrame(tiers)
    tier_summary = tier_weekly.groupby(['model', 'tier'], as_index=False).agg(
        correct_picks=('correct_picks', 'sum'), total_picks=('total_picks', 'sum'),
        hit_rate=('hit_rate', 'mean'), mean_rank_error=('mean_rank_error', 'mean'),
    )
    tier_summary['hit_rate'] = (tier_summary['hit_rate'] * 100).round(2)
    tier_summary['mean_rank_error'] = tier_summary['mean_rank_error'].round(4)
    summaries = []
    for model, group in predictions.groupby('model'):
        error = group['projected_ppr'].to_numpy() - group['actual_ppr'].to_numpy()
        summaries.append({
            'model': model, 'observations': len(group),
            'mae': round(float(np.abs(error).mean()), 4),
            'rmse': round(float(np.sqrt(np.mean(error ** 2))), 4),
            'correlation': round(float(group['projected_ppr'].corr(group['actual_ppr'])), 4),
            'mean_absolute_rank_error': round(float(group['absolute_rank_error'].mean()), 4),
        })
    summary = pd.DataFrame(summaries)
    OUT.mkdir(parents=True, exist_ok=True)
    prefix = OUT / f'{args.season}-rb-model-j2'
    predictions.to_csv(f'{prefix}-predictions.csv', index=False)
    summary.to_csv(f'{prefix}-summary.csv', index=False)
    tier_weekly.to_csv(f'{prefix}-tier-weekly.csv', index=False)
    tier_summary.to_csv(f'{prefix}-tier-summary.csv', index=False)
    print(f'\n{args.season} Model F / I / J1 / J2 comparison:')
    print(summary.to_string(index=False))
    print(tier_summary.to_string(index=False))
    print('Validation-only outputs written; production unchanged.')


if __name__ == '__main__':
    main()
