import json
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


def normalized_name(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace('’', "'")
    text = re.sub(r'[^a-z0-9]', '', text)
    return text


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
        record = matches[0].get('ownership')
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
    return verified, checked_at


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


def main():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    players = data.get('player_lookup', {})
    opportunities = data.get('opportunity_volume', {})
    performances = data.get('recent_player_performance', {})
    red_zone = data.get('red_zone_opportunity', {})

    # Fetch fresh public ownership each run. On failure, do not use old data.
    try:
        ownership, checked_at = fetch_espn_ownership(players)
    except Exception as error:
        print(f'ESPN ownership unavailable: {type(error).__name__}: {error}')
        ownership, checked_at = {}, None
    OWNERSHIP_SOURCE.write_text(json.dumps({
        'checked_at': checked_at, 'source': 'ESPN public fantasy player API',
        'players': ownership,
    }, indent=2) + '\n', encoding='utf-8')

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
            **ownership_summary(ownership.get(player_id, {})),
            'injury_opportunity': None,
        })
    candidates.sort(key=lambda player: (
        player['opportunity_change'] is not None,
        player['opportunity_change'] if player['opportunity_change'] is not None
        else float('-inf'), player['latest_opportunity']), reverse=True)
    result = {'season': data['season'], 'target_week': data['target_week'],
              'status': 'candidates_only', 'ownership_cutoff': OWNERSHIP_CUTOFF,
              'ownership_rule': 'available_verified_average',
              'ownership_minimum_sources': 1, 'candidates': candidates[:50]}
    OUTPUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    verified_count = sum(c['ownership_source_count'] > 0 for c in result['candidates'])
    eligible_count = sum(c['ownership_eligible'] is True for c in result['candidates'])
    print(f'Generated {len(result["candidates"])} waiver candidates.')
    print(f'Candidates with verified ownership: {verified_count}')
    print(f'Candidates below {OWNERSHIP_CUTOFF}% ownership: {eligible_count}')
    print('Final waiver recommendations remain pending injury analysis.')


if __name__ == '__main__':
    main()
