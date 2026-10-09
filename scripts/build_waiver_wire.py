import csv
import io
import json
import math
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = Path('nfl-stats.json')
OWNERSHIP_SOURCE = Path('waiver_wire_ownership.json')
OUTPUT = Path('waiver_wire_candidates.json')
OWNERSHIP_CUTOFF = 65
VALID_PLATFORMS = ('espn', 'yahoo', 'sleeper')
ESPN_URL = ('https://lm-api-reads.fantasy.espn.com/apis/v3/'
            'games/ffl/seasons/2026/players?scoringPeriodId=0&view=kona_player_info')
POSITION_IDS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE'}
FRESHNESS_HOURS = 36
NFLVERSE_INJURIES_URL = ('https://github.com/nflverse/nflverse-data/releases/'
                          'download/injuries/injuries_{season}.csv')
NFLVERSE_SCHEDULE_URL = (
    'https://raw.githubusercontent.com/'
    'nflverse/nfldata/master/data/games.csv'
)
# ESPN fantasy injuryStatus is an early warning, NOT official game-day clearance.
ESPN_UNAVAILABLE_STATUSES = {'OUT', 'DOUBTFUL', 'INJURY_RESERVE', 'IR', 'SUSPENSION', 'SUSPENDED', 'PUP', 'NFI'}


def normalized_name(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace('’', "'")
    text = re.sub(r'[^a-z0-9]', '', text)
    return text
def fetch_nfl_schedule(season):
    """Return regular-season team/week schedule coverage."""
    request = urllib.request.Request(
        NFLVERSE_SCHEDULE_URL,
        headers={'User-Agent': 'Mozilla/5.0'},
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read().decode('utf-8-sig')

    reader = csv.DictReader(io.StringIO(payload))
    required = {
        'season', 'week', 'game_type',
        'home_team', 'away_team',
    }

    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError('NFL schedule is missing required columns')

    team_weeks = defaultdict(set)
    game_count = 0

    for row in reader:
        try:
            row_season = int(row['season'])
            row_week = int(row['week'])
        except (TypeError, ValueError):
            continue

        if row_season != int(season):
            continue

        if row['game_type'] != 'REG':
            continue

        if row_week < 1:
            continue

        home_team = str(row['home_team'] or '').strip().upper()
        away_team = str(row['away_team'] or '').strip().upper()

        if not home_team or not away_team:
            continue

        team_weeks[home_team].add(row_week)
        team_weeks[away_team].add(row_week)
        game_count += 1

    if game_count < 200:
        raise ValueError(
            'NFL schedule coverage insufficient for requested season'
        )

    return team_weeks, game_count

def fetch_espn_ownership(players):
    params = {
        "players": {
            "limit": 2000,
            "sortPercOwned": {
                "sortPriority": 1,
                "sortAsc": False,
            },
        },
    }

    request = urllib.request.Request(
        ESPN_URL,
        headers={
            "Accept": "application/json",
            "X-Fantasy-Filter": json.dumps(params),
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        espn_players = json.load(response)
    if not isinstance(espn_players, list) or len(espn_players) < 500:
        raise RuntimeError('ESPN player pool response is incomplete.')

    # Establish ESPN proTeamId -> NFL team abbreviation using independent,
    # exact name + position matches. Require a clear consensus per team.
    nfl_by_identity = defaultdict(list)
    for pid, player in players.items():
        position = str(player.get('position') or '').upper()
        name = normalized_name(player.get('name'))
        team = str(player.get('team') or '').upper()
        if position in POSITION_IDS.values() and name and team:
            nfl_by_identity[(name, position)].append((pid, team))

    votes = defaultdict(Counter)
    for player in espn_players:
        if not isinstance(player, dict):
            continue
        position = POSITION_IDS.get(player.get('defaultPositionId'))
        key = (normalized_name(player.get('fullName')), position)
        matches = nfl_by_identity.get(key, [])
        espn_team = player.get('proTeamId')
        if len(matches) == 1 and isinstance(espn_team, int) and espn_team > 0:
            votes[espn_team][matches[0][1]] += 1

    team_map = {}
    for espn_id, counts in votes.items():
        top = counts.most_common(2)
        if top and top[0][1] >= 3 and (len(top) == 1 or top[0][1] >= 3 * top[1][1]):
            team_map[espn_id] = top[0][0]
    # Do not allow multiple ESPN team IDs to resolve to the same NFL team.
    reverse_counts = Counter(team_map.values())
    team_map = {eid: team for eid, team in team_map.items()
                if reverse_counts[team] == 1}

    by_identity = defaultdict(list)
    for espn_player in espn_players:
        if not isinstance(espn_player, dict):
            continue
        position = POSITION_IDS.get(espn_player.get('defaultPositionId'))
        team = team_map.get(espn_player.get('proTeamId'))
        key = (normalized_name(espn_player.get('fullName')), position, team)
        if position and team and key[0]:
            by_identity[key].append(espn_player)

    checked_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    verified = {}
    injury_reports = {}
    unmatched = 0
    ambiguous = 0
    for player_id, player in players.items():
        position = str(player.get('position') or '').upper()
        team = str(player.get('team') or '').upper()
        key = (normalized_name(player.get('name')), position, team)
        matches = by_identity.get(key, [])
        if len(matches) > 1:
            ambiguous += 1
            continue
        if not matches:
            unmatched += 1
            continue
        espn_record = matches[0]
        raw_status = espn_record.get('injuryStatus')
        if isinstance(raw_status, str) and raw_status.strip():
            status = raw_status.strip().upper()
            injury_reports[player_id] = {
                'status': status,
                'source': ESPN_URL,
                'checked_at': checked_at,
                'source_type': 'fantasy_player_feed_not_official_inactives',
            }
        record = espn_record.get('ownership')
        if not isinstance(record, dict):
            continue
        value = record.get('percentOwned')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            continue
        verified[player_id] = {'espn': {
            'percent': round(float(value), 2),
            'source': ESPN_URL,
            'checked_at': checked_at,
        }}

    print(f'ESPN: {len(espn_players)} players, {len(team_map)} mapped teams, '
          f'{len(verified)} verified ownership matches, '
          f'{unmatched} unmatched, {ambiguous} ambiguous.')
    if len(team_map) < 20 or len(verified) < 100:
        raise RuntimeError('ESPN coverage insufficient; refusing to publish ownership.')
    return verified, injury_reports, checked_at


def fetch_nflverse_injuries(season, week):
    """Read third-party injury evidence; never treat it as official clearance.

    The CSV has no publication or report timestamp. Retrieval time only proves
    when this script downloaded it, not when its observations were updated.
    """
    url = NFLVERSE_INJURIES_URL.format(season=int(season))
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    required = {'season', 'week', 'gsis_id', 'team', 'report_status',
                'practice_status', 'report_primary_injury', 'practice_primary_injury'}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError('nflverse injury CSV is missing required columns')
    matched_week = []
    for row in reader:
        try:
            if int(row['season']) == int(season) and int(row['week']) == int(week):
                matched_week.append(row)
        except (TypeError, ValueError):
            continue
    if not matched_week:
        raise ValueError('nflverse injury CSV has no rows for requested season/week')
    by_id = defaultdict(list)
    for row in matched_week:
        if row.get('gsis_id'):
            by_id[row['gsis_id']].append(row)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return by_id, {'source': url, 'retrieved_at': retrieved_at,
                   'report_updated_at': None, 'freshness': 'unverified_no_report_timestamp',
                   'week_record_count': len(matched_week)}


def nflverse_injury_evidence(player_id, team, reports, metadata):
    """Attach evidence only for unique ID and team matches; do not infer health."""
    rows = reports.get(player_id, [])
    matches = [row for row in rows if row.get('team') == team]
    result = {
        'nflverse_injury_match': 'not_listed',
        'nflverse_practice_status': None,
        'nflverse_practice_injury': None,
        'nflverse_game_status': None,
        'nflverse_report_injury': None,
        'nflverse_source': metadata.get('source'),
        'nflverse_retrieved_at': metadata.get('retrieved_at'),
        'nflverse_report_updated_at': None,
        'nflverse_freshness': metadata.get('freshness', 'unavailable'),
    }
    if not rows:
        return result
    if len(matches) != 1 or len(rows) != 1:
        result['nflverse_injury_match'] = 'ambiguous_or_team_mismatch'
        return result
    row = matches[0]
    result.update({
        'nflverse_injury_match': 'matched',
        'nflverse_practice_status': row.get('practice_status') or None,
        'nflverse_practice_injury': row.get('practice_primary_injury') or None,
        'nflverse_game_status': row.get('report_status') or None,
        'nflverse_report_injury': row.get('report_primary_injury') or None,
    })
    return result


def load_ownership():
    if not OWNERSHIP_SOURCE.exists():
        return {}
    data = json.loads(OWNERSHIP_SOURCE.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('players', {}), dict):
        raise ValueError('Ownership file must contain a players object.')
    return data.get('players', {})


def verified_ownership(record):
    verified = {}
    if not isinstance(record, dict):
        return verified
    now = datetime.now(timezone.utc)
    for platform in VALID_PLATFORMS:
        entry = record.get(platform)
        if not isinstance(entry, dict):
            continue
        value, source, checked_at = (entry.get('percent'), entry.get('source'),
                                     entry.get('checked_at'))
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not 0 <= value <= 100 or not isinstance(source, str)
                or not source.strip() or not isinstance(checked_at, str)):
            continue
        try:
            timestamp = datetime.fromisoformat(checked_at.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                continue
            age = now - timestamp.astimezone(timezone.utc)
            if not timedelta(0) <= age <= timedelta(hours=FRESHNESS_HOURS):
                continue
        except ValueError:
            continue
        verified[platform] = {'percent': round(float(value), 2),
                              'source': source.strip(), 'checked_at': checked_at}
    return verified


def ownership_summary(record):
    verified = verified_ownership(record)
    if not verified:
        return {'espn_rostered': None, 'yahoo_rostered': None,
                'sleeper_rostered': None, 'average_rostered': None,
                'ownership_eligible': None, 'ownership_sources': {},
                'ownership_source_count': 0}
    average = sum(item['percent'] for item in verified.values()) / len(verified)
    return {'espn_rostered': verified.get('espn', {}).get('percent'),
            'yahoo_rostered': verified.get('yahoo', {}).get('percent'),
            'sleeper_rostered': verified.get('sleeper', {}).get('percent'),
            'average_rostered': round(average, 2),
            'ownership_eligible': average < OWNERSHIP_CUTOFF,
            'ownership_sources': verified, 'ownership_source_count': len(verified)}



def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def percentile_scores(candidates, field):
    """Relative 0-100 evidence score; missing data stays missing."""
    available = sorted({value for candidate in candidates
                        if (value := finite_number(candidate.get(field))) is not None})
    if not available:
        return {}
    if len(available) == 1:
        return {available[0]: 50.0}
    return {value: round(100 * index / (len(available) - 1), 2)
            for index, value in enumerate(available)}


def rank_eligible_candidates(candidates):
    """Position-relative evidence ranking; not final pickup recommendations."""
    eligible = [c for c in candidates if c['ownership_eligible'] is True]
    weights = {
        'opportunity_change': 0.45,
        'recent_average_ppr': 0.35,
        'latest_opportunity': 0.20,
    }
    by_position = defaultdict(list)
    for candidate in eligible:
        by_position[candidate['position']].append(candidate)
    position_maps = {
        position: {
            field: percentile_scores(group, field)
            for field in weights
        }
        for position, group in by_position.items()
    }
    for candidate in eligible:
        evidence = {}
        missing = []
        for field, weight in weights.items():
            value = finite_number(candidate.get(field))
            if value is None:
                missing.append(field)
                continue
            percentile = position_maps[candidate['position']][field][value]
            evidence[field] = {
                'value': round(value, 2),
                'percentile': percentile,
                'weight': weight,
            }
        # Fixed denominator: missing evidence receives no credit rather than
        # allowing strong known metrics to inflate the overall score.
        score = sum(item['percentile'] * item['weight']
                    for item in evidence.values())
        candidate['waiver_evidence_score'] = round(score, 2)
        candidate['waiver_evidence'] = evidence
        candidate['waiver_missing_evidence'] = missing
        candidate['waiver_evidence_coverage'] = round(
            sum(item['weight'] for item in evidence.values()), 2
        )
        candidate['waiver_rank_status'] = 'preliminary_not_injury_verified'
        candidate['waiver_scoring_scope'] = 'within_position'

    eligible.sort(key=lambda c: (
        -c['waiver_evidence_score'],
        -c['waiver_evidence_coverage'],
        -(finite_number(c.get('opportunity_change')) or 0),
        str(c.get('name') or '').lower(),
        str(c.get('player_id') or ''),
    ))
    for index, candidate in enumerate(eligible, 1):
        candidate['preliminary_waiver_rank'] = index
        candidate['preliminary_position_rank'] = 0
    for position in POSITION_IDS.values():
        for index, candidate in enumerate(
            (c for c in eligible if c['position'] == position), 1
        ):
            candidate['preliminary_position_rank'] = index
    return eligible


def usage_role_evidence(games, position):
    """Measured recent usage only; never infer official starting status."""
    recent = games[:3]
    fields = ('pass_attempts', 'carries', 'targets', 'receptions')
    history = []
    for game in recent:
        metrics = {}
        for field in fields:
            value = finite_number(game.get(field))
            metrics[field] = round(value, 2) if value is not None else None
        history.append({'season': game.get('season'), 'week': game.get('week'), **metrics})
    averages = {}
    for field in fields:
        values = [entry[field] for entry in history if entry[field] is not None]
        averages[field] = round(sum(values) / len(values), 2) if values else None
    return {
        'usage_evidence_status': 'measured_usage_only_not_role_verified',
        'usage_sample_games': len(history),
        'usage_weekly_history': history,
        'usage_recent_3_game_averages': averages,
        'usage_primary_metric': 'pass_attempts' if position == 'QB' else ('carries' if position == 'RB' else 'targets'),
        'offensive_snap_share': None,
        'official_depth_chart_role': None,
        'starting_role_verified': None,
        'injury_replacement_role_verified': None,
    }


def injury_screening(report):
    """Flag explicit negative fantasy injury statuses; never assert cleared."""
    if not isinstance(report, dict) or not report.get('status'):
        return {'injury_feed_status': None, 'injury_feed_source': None,
                'injury_feed_checked_at': None, 'injury_screening': 'unverified',
                'injury_screening_reason': 'No matched ESPN injury status'}
    status = report['status']
    flagged = status in ESPN_UNAVAILABLE_STATUSES
    return {'injury_feed_status': status,
            'injury_feed_source': report['source'],
            'injury_feed_checked_at': report['checked_at'],
            'injury_screening': 'flagged_unavailable' if flagged else 'requires_official_verification',
            'injury_screening_reason': (
                'ESPN fantasy feed lists an unavailable status; verify official report'
                if flagged else 'ESPN fantasy feed does not establish game-day availability')}



def injury_review_priority(candidate):
    """Prioritize manual verification without claiming official clearance."""
    status = str(candidate.get('injury_feed_status') or '').upper()
    if candidate.get('injury_screening') == 'flagged_unavailable':
        return 'blocked_by_espn_screen'
    if status in {'QUESTIONABLE', 'DOUBTFUL', 'GTD', 'DAY_TO_DAY'}:
        return 'high_injury_verification_priority'
    if not status or status in {'UNKNOWN', 'UNVERIFIED'}:
        return 'high_missing_status_verification_priority'
    return 'standard_official_verification_pending'


def build_provisional_shortlist(eligible, limit=10):
    """Keep evidence ranks unchanged; skip ESPN-flagged unavailable players.

    This is a review shortlist only, not an official injury clearance or
    published pickup recommendation. Consider the full eligible pool so
    excluded top-ranked players can be replaced fairly.
    """
    selected = []
    excluded = []
    for candidate in eligible:
        if candidate.get('injury_screening') == 'flagged_unavailable':
            if candidate.get('preliminary_waiver_rank', 10**9) <= limit:
                excluded.append({
                    'player_id': candidate['player_id'],
                    'name': candidate['name'],
                    'original_rank': candidate['preliminary_waiver_rank'],
                    'injury_feed_status': candidate.get('injury_feed_status'),
                    'reason': candidate.get('injury_screening_reason'),
                })
            continue
        if len(selected) < limit:
            selected.append({
                'player_id': candidate['player_id'],
                'name': candidate['name'],
                'team': candidate['team'],
                'position': candidate['position'],
                'original_rank': candidate['preliminary_waiver_rank'],
                'provisional_rank': len(selected) + 1,
                'role_usage_evidence': candidate.get('role_usage_evidence'),
                'waiver_evidence_score': candidate['waiver_evidence_score'],
                'average_rostered': candidate['average_rostered'],
                'injury_feed_status': candidate.get('injury_feed_status'),
                'injury_screening': candidate.get('injury_screening'),
                'injury_review_priority': injury_review_priority(candidate),
                'nflverse_injury_match': candidate.get('nflverse_injury_match'),
                'nflverse_practice_status': candidate.get('nflverse_practice_status'),
                'nflverse_practice_injury': candidate.get('nflverse_practice_injury'),
                'nflverse_game_status': candidate.get('nflverse_game_status'),
                'nflverse_report_injury': candidate.get('nflverse_report_injury'),
                'nflverse_source': candidate.get('nflverse_source'),
                'nflverse_retrieved_at': candidate.get('nflverse_retrieved_at'),
                'nflverse_report_updated_at': None,
                'nflverse_freshness': candidate.get('nflverse_freshness'),
                'injury_source_conflict_review': bool(
                    candidate.get('nflverse_game_status') and
                    candidate.get('injury_feed_status') and
                    candidate['nflverse_game_status'].strip().upper() !=
                    candidate['injury_feed_status'].strip().upper()),
                'injury_feed_source': candidate.get('injury_feed_source'),
                'injury_feed_checked_at': candidate.get('injury_feed_checked_at'),
                'official_game_status': None,
                'official_game_status_source': None,
                'official_game_status_checked_at': None,
                'starting_role_verified': None,
                'injury_opportunity_verified': None,
                'matchup_verified': None,
                'verification_status': 'official_injury_role_matchup_pending',
            })
        if len(selected) >= limit and candidate['preliminary_waiver_rank'] > limit:
            break
    return selected, excluded


def main():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    players = data.get('player_lookup', {})
    opportunities = data.get('opportunity_volume', {})
    performances = data.get('recent_player_performance', {})
    red_zone = data.get('red_zone_opportunity', {})

    # Fetch fresh public ownership each run. On failure, do not use old data.
    try:
        ownership, injury_reports, checked_at = fetch_espn_ownership(players)
    except Exception as error:
        print(f'ESPN ownership unavailable: {type(error).__name__}: {error}')
        ownership, injury_reports, checked_at = {}, {}, None
    OWNERSHIP_SOURCE.write_text(json.dumps({
        'checked_at': checked_at, 'source': 'ESPN public fantasy player API',
        'players': ownership,
    }, indent=2) + '\n', encoding='utf-8')

    try:
        nflverse_reports, nflverse_metadata = fetch_nflverse_injuries(
            data['season'], data['target_week'])
        print('nflverse injury records for target week: ' +
              str(nflverse_metadata['week_record_count']))
    except Exception as error:
        print(f'nflverse injuries unavailable: {type(error).__name__}: {error}')
        nflverse_reports = {}
        nflverse_metadata = {
            'source': NFLVERSE_INJURIES_URL.format(season=int(data['season'])),
            'retrieved_at': None, 'report_updated_at': None,
            'freshness': 'unavailable', 'week_record_count': 0,
        }

    try:
        team_weeks, schedule_game_count = fetch_nfl_schedule(data['season'])
        print(
            f"NFL schedule loaded: {schedule_game_count} games, "
            f"{len(team_weeks)} teams."
        )
    except Exception as error:
        raise RuntimeError(
            f"NFL schedule verification failed: {error}"
        ) from error

    unknown_team_codes = sorted({
        str(player.get('team') or '').strip().upper()
        for player in players.values()
        if player.get('position') in {'QB', 'RB', 'WR', 'TE'}
        and str(player.get('team') or '').strip().upper() not in team_weeks
    })
    print(f"Player team codes missing from NFL schedule: {unknown_team_codes}")

    candidates = []
    for player_id, player in players.items():
        position = player.get('position')
        if position not in {'QB', 'RB', 'WR', 'TE'}:
            continue
        games = opportunities.get(player_id, {}).get('games', [])
        current_games = [game for game in games
                         if int(game.get('season', 0)) == data['season']]
        current_games.sort(key=lambda game: int(game.get('week', 0)), reverse=True)
        if not current_games:
            continue
        latest_recorded_week = int(current_games[0].get('week', 0))
        latest_completed_week = int(data['target_week']) - 1

        team = str(player.get('team') or '').strip().upper()
        schedule_team = 'LA' if team == 'LAR' else team

        missed_scheduled_weeks = [
            week
            for week in range(latest_recorded_week + 1, latest_completed_week + 1)
            if week in team_weeks.get(schedule_team, set()))
        ]

        if missed_scheduled_weeks:
            continue
        latest = float(current_games[0].get('opportunity_value') or 0)
        previous = [float(game.get('opportunity_value') or 0)
                    for game in current_games[1:4]]
        baseline = sum(previous) / len(previous) if previous else None
        change = round(latest - baseline, 2) if baseline is not None else None
        performance = performances.get(player_id, {})
        red_zone_data = red_zone.get(player_id, {})
        candidates.append({
            'player_id': player_id, 'name': player.get('name'),
            'team': player.get('team'), 'position': position,
            'latest_opportunity': latest,
            'previous_opportunity_average': (round(baseline, 2)
                                             if baseline is not None else None),
            'opportunity_change': change,
            'recent_average_ppr': performance.get('average_ppr'),
            'red_zone_score': red_zone_data.get('score'),
            'role_usage_evidence': usage_role_evidence(current_games, position),
            **ownership_summary(ownership.get(player_id, {})),
            'injury_opportunity': None,
            **injury_screening(injury_reports.get(player_id)),
            **nflverse_injury_evidence(player_id, player.get('team'),
                                       nflverse_reports, nflverse_metadata),
        })
    # Do not truncate before filtering: eligible players outside the first
    # 50 opportunity-growth records must remain eligible for consideration.
    eligible = rank_eligible_candidates(candidates)
    unverified = [c for c in candidates if c['ownership_eligible'] is None]
    above_cutoff = [c for c in candidates if c['ownership_eligible'] is False]

    # Keep a 50-player review pool for the existing website. Only players
    # with verified ownership below 65% enter the ranked portion.
    review_pool = eligible[:50]
    provisional_top_10, excluded_top_10 = build_provisional_shortlist(eligible)
    result = {
        'season': data['season'],
        'target_week': data['target_week'],
        'status': 'preliminary_ownership_filtered_not_injury_verified',
        'ownership_cutoff': OWNERSHIP_CUTOFF,
        'ownership_rule': 'available_verified_average',
        'ownership_minimum_sources': 1,
        'ranking_method': 'within_position_percentiles_fixed_missing_denominator',
        'ranking_weights': {
            'opportunity_change': 0.45,
            'recent_average_ppr': 0.35,
            'latest_opportunity': 0.20,
        },
        'missing_evidence_policy': 'zero_contribution_fixed_denominator',
        'cross_position_rank_status': 'preliminary_not_role_or_injury_adjusted',
        'role_evidence_policy': 'observed_last_three_games_only_no_official_starter_or_snap_share_inference',
        'injury_analysis_status': 'fantasy_feed_screening_only_official_verification_pending',
        'injury_screening_source': 'ESPN fantasy player API injuryStatus (when provided)',
        'injury_screening_not_official_clearance': True,
        'nflverse_injury_metadata': nflverse_metadata,
        'nflverse_injury_policy': 'supplemental_unverified_freshness_never_official_clearance',
        'full_candidate_count': len(candidates),
        'eligible_candidate_count': len(eligible),
        'unverified_ownership_count': len(unverified),
        'above_cutoff_count': len(above_cutoff),
        'candidates': review_pool,
        'provisional_top_10_status': 'review_only_not_officially_verified_or_published',
        'provisional_verification_policy': 'ESPN statuses only prioritize review; official clearance, role, injury opportunity, and matchup remain unverified',
        'provisional_top_10': provisional_top_10,
        'excluded_from_original_top_10_by_espn_injury_screen': excluded_top_10,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'Full opportunity candidate pool: {len(candidates)}')
    print(f'Players with verified ownership below {OWNERSHIP_CUTOFF}%: {len(eligible)}')
    print(f'Players with unverified ownership: {len(unverified)}')
    print(f'Players at or above {OWNERSHIP_CUTOFF}%: {len(above_cutoff)}')
    print(f'Preliminary ranked candidates saved: {len(review_pool)}')
    print('Top 50 position counts: ' + ', '.join(
        f'{pos}={sum(c["position"] == pos for c in review_pool)}'
        for pos in ('QB', 'RB', 'WR', 'TE')))
    print('Top 10 position counts: ' + ', '.join(
        f'{pos}={sum(c["position"] == pos for c in review_pool[:10])}'
        for pos in ('QB', 'RB', 'WR', 'TE')))
    print('Provisional Top 10 with measured role usage: ' + str(sum(
        bool(c.get('role_usage_evidence', {}).get('usage_sample_games'))
        for c in provisional_top_10)))
    print('Injury-screened provisional Top 10: ' + str(len(provisional_top_10)))
    print('Original Top 10 flagged unavailable: ' + str(len(excluded_top_10)))
    print('Provisional Top 10 original ranks: ' + ', '.join(
        str(c['original_rank']) for c in provisional_top_10))
    print('Provisional Top 10 high-priority injury reviews: ' + str(sum(
        c['injury_review_priority'].startswith('high_') for c in provisional_top_10)))
    print('Provisional Top 10 questionable statuses: ' + str(sum(
        c['injury_feed_status'] == 'QUESTIONABLE' for c in provisional_top_10)))
    print('Top 50 ESPN injury flags: ' + str(sum(
        c['injury_screening'] == 'flagged_unavailable' for c in review_pool)))
    print('Top 50 missing ESPN injury status: ' + str(sum(
        c['injury_screening'] == 'unverified' for c in review_pool)))
    print('Provisional Top 10 nflverse ID/team matches: ' + str(sum(
        c['nflverse_injury_match'] == 'matched' for c in provisional_top_10)))
    print('Provisional Top 10 nflverse source conflicts to review: ' + str(sum(
        c['injury_source_conflict_review'] for c in provisional_top_10)))
    print('nflverse injury report freshness: ' + nflverse_metadata['freshness'])
    print('No final Top 10 published: official injuries, role and matchup evaluation remain pending.')



if __name__ == '__main__':
    main()
