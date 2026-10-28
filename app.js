
const BASE_WEIGHTS = {
  opportunity: 0.1674,
  production: 0.2046,
  usage: 0.1395,
  playCallerMatchup: 0.0651,
  playerVsDefensiveCaller: 0.0651,
  redzone: 0.093,
  matchup: 0.093,
  expert: 0.0558,
  risk: 0.0465,
  trench: 0.07
};

function getUsageEvidence(player) {
  const games = getPlayerWeeklyStats(player)
    .filter(game => Number(game.season) === 2026)
    .sort((a, b) =>
      Number(b.week || 0) - Number(a.week || 0)
    )
    .slice(0, 3);

  if (games.length === 0) {
    return "2026 · 0 games · no player data (fallback: 20)";
  }

  let validGames = 0;

  games.forEach(game => {
    const season = Number(game.season);
    const week = Number(game.week);
    const team = game.team;

    if (!season || !week || !team) return;

    const rows = getTeamGameRows(season, week, team);

    const teamCarries = rows.reduce(
      (sum, row) =>
        sum + Number(
          row.carries || row.rushing_attempts || 0
        ),
      0
    );

    if (player.position === "QB") {
      if (teamCarries > 0) validGames++;
      return;
    }

    // RB/WR/TE usage accepts a valid team-week
    // even when either individual denominator is zero.
    validGames++;
  });

  return (
    `Last 3 available games · ${validGames} valid ` +
    `of ${games.length} selected · ` +
    (validGames === 0
      ? "neutral fallback: 50"
      : validGames < 3
        ? "limited sample"
        : "team opportunity shares")
  );
}

let currentWeightedRedZoneData = null;

async function loadWeightedRedZoneData() {
  currentWeightedRedZoneData = null;

  const week = Number(
    document.documentElement.dataset.targetWeek
  );

  if (!Number.isInteger(week) || week < 2 || week > 19) {
    return;
  }

  try {
    const response = await fetch(
      `./data/red_zone_usage_2026_week${week}.json`,
      { cache: "no-store" }
    );

    if (!response.ok) {
      console.warn("Weighted red-zone feed unavailable:", response.status);
      return;
    }

    const data = await response.json();

    if (
      Number(data.season) !== 2026 ||
      Number(data.target_week) !== week ||
      !data.players ||
      !Number.isFinite(
        Number(data.league_high_weighted_opportunities_per_game)
      )
    ) {
      console.warn("Invalid weighted red-zone feed");
      return;
    }

    currentWeightedRedZoneData = data;
  } catch (error) {
    console.warn("Could not load weighted red-zone feed:", error);
  }
}

function getWeightedRedZoneRecord(player) {
  if (
    !currentWeightedRedZoneData ||
    !["RB", "WR", "TE"].includes(player.position)
  ) {
    return null;
  }

  const playerId = String(
    player.player_id || player.id || ""
  ).trim();

  const name = normalizeName(player.name)
    .replace(/\s+(jr|sr|ii|iii|iv|v)$/i, "");
  const matches = Object.entries(
    currentWeightedRedZoneData.players
  ).filter(([id, record]) =>
    record.position === player.position &&
    (
      (playerId && id === playerId) ||
      normalizeName(record.player_name)
        .replace(/\s+(jr|sr|ii|iii|iv|v)$/i, "") === name    )
  );

  return matches.length === 1 ? matches[0][1] : null;
}

function getWeightedRedZoneEvidence(player) {
  const record = getWeightedRedZoneRecord(player);

  if (!record) {
    return "Weighted red-zone data unavailable";
  }

  const zones = [
    ["20–11 yards", "20_11"],
    ["10–6 yards", "10_6"],
    ["Inside the 5", "5_1"]
  ];

  const details = zones.map(([label, key]) => {
    const zone = record.zones[key];
    const opportunities = zone.carries + zone.targets;
    return `${label}: ${opportunities} (${zone.carries} carries, ${zone.targets} targets)`;
  });

  return (
    `Last ${record.games_evaluated} completed games · ` +
    details.join(" · ") +
    ` · Weighted opportunities/game: ` +
    Number(record.weighted_opportunities_per_game).toFixed(2)
  );
}



let currentGoalLineData = null;


async function loadGoalLineData() {
  currentGoalLineData = null;

  const currentWeek = Number(
    document.documentElement.dataset.targetWeek
  );

  if (
    !Number.isInteger(currentWeek) ||
    currentWeek < 2 ||
    currentWeek > 19
  ) {
    return;
  }

  try {
    const response = await fetch(
      `./data/rb_goal_line_2026_week${currentWeek}.json`,
      { cache: "no-store" }
    );

    if (!response.ok) {
      console.warn(
        `Goal-line data unavailable for Week ${currentWeek}:`,
        response.status
      );
      return;
    }

    const data = await response.json();

    if (
      Number(data.season) !== 2026 ||
      Number(data.target_week) !== currentWeek ||
      !data.players
    ) {
      console.warn("Goal-line feed week mismatch");
      return;
    }

    currentGoalLineData = data;
  } catch (error) {
    console.warn("Goal-line data unavailable:", error);
  }
}

function getGoalLineEvidence(player) {
  if (
    !currentGoalLineData ||
    player.position !== "RB"
  ) {
    return null;
  }

  const playerId = String(
    player.player_id || player.id || ""
  ).trim();

  const playerName = normalizeName(player.name);

  const record = Object.entries(
    currentGoalLineData.players
  ).find(([id, entry]) =>
    (playerId && id === playerId) ||
    normalizeName(entry.player_name) === playerName
  );

  if (!record) {
    return "Inside-the-5: player data unavailable";
  }

  const entry = record[1];
  const carries = Number(
    entry.inside5_rushes_last3weeks || 0
  );
  const targets = Number(
    entry.inside5_targets_last3weeks || 0
  );
  const teamCarries = Number(
    entry.team_inside5_rushes_last3weeks || 0
  );

  const share = entry.inside5_rush_share_last3weeks;

  return (
    `Inside-the-5, previous 3 calendar weeks: ` +
    `${carries} carries, ${targets} targets · ` +
    (share === null
      ? "No team goal-line rushing opportunities"
      : `${carries} of ${teamCarries} team carries ` +
        `(${(Number(share) * 100).toFixed(1)}%)`)
  );
}


function getRedZoneEvidence(player) {
  const games = getPlayerWeeklyStats(player)
    .filter(game => Number(game.season) === 2026)
    .sort((a, b) =>
      Number(b.week || 0) - Number(a.week || 0)
    )
    .slice(0, 3);

  if (games.length === 0) {
    return "2026 · 0 games · neutral fallback: 50";
  }

  if (player.position === "QB") {
    const matchingGames = weeklyStats
      .filter(game =>
        Number(game.season) === 2026 &&
        game.position === "QB" &&
        normalizeName(
          game.player_display_name ||
          game.player_name ||
          game.name
        ) === normalizeName(player.name)
      )
      .sort((a, b) =>
        Number(b.week || 0) - Number(a.week || 0)
      )
      .slice(0, 3);

    return (
      `Last 3 available QB games · ` +
      `${matchingGames.length} evaluated · ` +
      `red-zone passes + carries` +
      (matchingGames.length < 3
        ? " · limited sample"
        : "")
    );
  }

  const validGames = games.filter(game =>
    Number.isFinite(Number(game.season)) &&
    Number.isFinite(Number(game.week))
  );

  
  const goalLineEvidence = getGoalLineEvidence(player);

  return (
    `Last 3 available games · ` +
    `${validGames.length} evaluated · ` +
    (player.position === "RB"
      ? "red-zone carries"
      : "red-zone targets") +
    (validGames.length === 0
      ? " · neutral fallback: 50"
      : validGames.length < 3
        ? " · limited sample"
        : "") +
    (goalLineEvidence
      ? ` · ${goalLineEvidence}`
      : "")
  );
}

function getConfidenceEvidence(player) {
  const count = getPlayerWeeklyStats(player)
    .filter(game => Number(game.season) === 2026)
    .sort((a, b) =>
      Number(b.week || 0) - Number(a.week || 0)
    )
    .slice(0, 3)
    .length;

  return (
    `Last 3 available games · ${count} evaluated · ` +
    (count < 2
      ? "neutral fallback: 50"
      : count < 3
        ? "limited sample + availability"
        : "stability + availability")
  );
}

function getRiskEvidence(player) {
  return (
    "Current player status · injury, practice, " +
    "roster, depth chart, experience and age · " +
    "rule-based; no game sample"
  );
}

const riskProfiles = {
  conservative: {
    opportunity: 0.15,
    production: 0.13,
    usage: 0.12,
    playCallerMatchup: 0.10,
    playerVsDefensiveCaller: 0.10,
    redzone: 0.10,
    matchup: 0.08,
    expert: 0.10,
    risk: 0.12
  },

  balanced: BASE_WEIGHTS,

  aggressive: {
    opportunity: 0.17,
    production: 0.17,
    usage: 0.12,
    playCallerMatchup: 0.13,
    playerVsDefensiveCaller: 0.13,
    redzone: 0.12,
    matchup: 0.08,
    expert: 0.05,
    risk: 0.03
  }
};
const metricDescriptions = {
  Opportunity: {
    weight: "16.74%",
    description:
      "Measures how often a player has the chance to produce compared with others at the same position. QB: pass attempts + carries. RB: carries + targets. WR/TE: targets + carries."
  },

  "Recent Production": {
  weight: "20.46%",
  description:
    "Measures average PPR fantasy production over the player's three most recent games compared with other players at the same position. The highest-scoring player at each position receives 100, with all other players scored proportionally."
},
  
Usage: {
  weight: "13.95%",
  description:
    "Measures a player's share of his team's offensive opportunities. QB measures recent rushing involvement relative to team rushing volume. RB, WR and TE combine team rushing-attempt share and team target share."
},
  
  Matchup: {
    weight: "9.30%",
    description:
      "Measures how many fantasy points the opposing defense has allowed to the player's position over its three most recent games this season compared with league average."
},


 
 
  "Red-Zone Usage": {
    weight: "9.30%",
    description:
      "Measures scoring opportunities near the goal line. " +
      "For RBs, WRs and TEs, carries and receiving targets over the previous four completed games are weighted by distance: " +
      "20–11 yards = 1×, 10–6 yards = 2×, and inside the 5 = 3×. " +
      "Their scores are relative to the position-group leader in weighted opportunities per game. " +
      "For QBs, a separate method evaluates red-zone passing attempts and carries over the three most recent available games."
  },

  "Model Confidence": {
    weight: "5.58%",
    description:
      "Measures how dependable the player's projection appears based on recent production consistency, opportunity stability, usage stability and availability."
  },
  
  "Play Caller Matchup": {
    weight: "6.51%",
    description:
      "Measures how the player's current offensive play caller has historically produced at this position against the upcoming opponent's defensive play caller. Uses up to the three most recent applicable meetings. No direct history receives a neutral score of 50."
  },
  
  "Player vs Defensive Play Caller": {
    weight: "6.51%",
    description:
      "Measures how this individual player has historically performed in PPR scoring against defenses called by the upcoming opponent's current defensive play caller. Uses up to the three most recent applicable games. No direct history receives a neutral score of 50."
},  
  "Scoring Environment": {
    weight: "7.00%",
    description:
      "Measures the offense's expected scoring environment for the upcoming game using the betting market's implied team total. Higher implied team totals indicate more expected scoring opportunities for touchdowns, yards and fantasy production."
  },
  
  "Risk Adjustment": {
    weight: "4.65%",
    description:
      "Measures player reliability using injury status, practice participation, roster status, depth-chart role, experience and age. A higher score means lower risk."
  }
};
let players = [];
let actualPprResults = [];
async function loadActualPprResults() {
  try {
    const response = await fetch("./data/actual-ppr-2026.json?v=" + Date.now(), {cache: "no-store"});
    if (!response.ok) return;
    const payload = await response.json();
    actualPprResults = Array.isArray(payload.players) ? payload.players : [];
    console.info("Actual PPR feed loaded", {
      rows: actualPprResults.length,
      week: document.documentElement.dataset.targetWeek,
      completedWeekRows: actualPprResults.filter(row =>
        Number(row.week) === Number(document.documentElement.dataset.targetWeek)
      ).length
    });
  } catch (error) {
    console.warn("Actual PPR results unavailable:", error);
  }
}
let weeklyStats = [];
let fantasyAiScores = {};
let nflPlayerLookup = {};
let defensePositionAllowed = {};
let teamNextOpponent = {};
let currentPlayCallerSignals = {};
let currentTrenchSignals = {};
let trenchSignalWeek = null;
let currentPlayerVsDefensiveCaller = {};
let currentScoringEnvironment = {};
let weeklyPprProjections = [];
let verifiedInjuryOutKeys = new Set();
let verifiedInjuryOutIds = new Set();
const pprProjectionByPlayerId = new Map();
const pprProjectionByPlayerKey = new Map();
const playerASelect = document.getElementById("playerA");
const playerBSelect = document.getElementById("playerB");
const riskSelect = document.getElementById("riskTolerance");
const compareButton = document.getElementById("compareBtn");
const resultsContainer = document.getElementById("result");
const playerASearch = document.getElementById("playerASearch");
const playerBSearch = document.getElementById("playerBSearch");
const playerCSearch = document.getElementById("playerCSearch");
const playerAResults = document.getElementById("playerAResults");
const playerBResults = document.getElementById("playerBResults");
const playerCResults = document.getElementById("playerCResults");
const playerCSelect = document.getElementById("playerC");
const urlParams = new URLSearchParams(window.location.search);
const snapshotWeek = urlParams.get("snapshotWeek");

const statsFile = snapshotWeek
  ? `./nfl-stats-week${snapshotWeek}-snapshot.json`
  : "./nfl-stats.json";

async function loadTrenchRateDetails() {
  try {
    const response = await fetch("./data/trench-rate-details.json?v=" + Date.now(), { cache: "no-store" });
    if (!response.ok) return;
    const details = await response.json();
    if (Number(details.season) !== 2026 || Number(details.week) !== Number(trenchSignalWeek)) return;
    const normalize = team => team === "LAR" ? "LA" : team;
    for (const [team, rates] of Object.entries(details.teams || {})) {
      const record = currentTrenchSignals[team] || currentTrenchSignals[normalize(team)] || currentTrenchSignals[team === "LA" ? "LAR" : team];
      if (!record || record.available !== true ||
          normalize(record.defense_team) !== normalize(rates.defense_team)) continue;
      for (const field of ["offense_sack_rate", "offense_qb_hit_rate", "offense_rush_success_rate",
        "defense_sack_rate", "defense_qb_hit_rate", "defense_run_stop_rate"]) {
        if (rates[field] != null && Number.isFinite(Number(rates[field]))) record[field] = Number(rates[field]);
      }
    }
  } catch (error) {
    console.warn("Optional trench rate details unavailable", error);
  }
}
async function loadWeeklyStats() {
  try {
const response = await fetch(
  `${statsFile}?v=${Date.now()}`,
  { cache: "no-store" }
);
    if (!response.ok) {
      throw new Error(
        `Could not load ${statsFile}: ${response.status}`
      );
    }

    const data = await response.json();

weeklyStats = data.players || [];
await loadActualPprResults();
fantasyAiScores = data.fantasy_ai_scores || {};
nflPlayerLookup = data.player_lookup || {};

playerWeeklyStatsCache.clear();
    teamGameStatsCache.clear();
    playerMetricsCache.clear();
    defensePositionAllowed =
      data.defense_position_allowed || {};
    teamNextOpponent =
      data.team_next_opponent || {};
 
currentPlayCallerSignals =
  data.current_play_caller_signals || {};

currentTrenchSignals =
  data.current_trench_signals || {};

trenchSignalWeek =
  data.target_week || null;

currentScoringEnvironment =
  data.current_scoring_environment || {};


const publishedWeek = Number(data.target_week);

const easternToday = new Intl.DateTimeFormat(
  "en-CA",
  {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }
).formatToParts(new Date());

const dateParts = Object.fromEntries(
  easternToday.map(part => [part.type, part.value])
);

const easternDate = Date.UTC(
  Number(dateParts.year),
  Number(dateParts.month) - 1,
  Number(dateParts.day)
);

// The 2026 NFL Week 1 publishing window begins
// Tuesday, September 8. Each following week
// begins on Tuesday Eastern Time.
const firstWeekStart = Date.UTC(2026, 8, 8);

const calendarWeek = Math.max(
  1,
  Math.min(
    18,
    Math.floor(
      (easternDate - firstWeekStart) /
      (7 * 24 * 60 * 60 * 1000)
    ) + 1
  )
);

const displayWeek = Number.isInteger(publishedWeek) &&
  publishedWeek >= 1
    ? Math.min(publishedWeek, calendarWeek)
    : calendarWeek;

document.documentElement.dataset.targetWeek =
  String(displayWeek);

const matchupWeekAligned =
  publishedWeek === displayWeek;

document.documentElement.dataset.matchupWeekAligned =
  String(matchupWeekAligned);

if (!matchupWeekAligned) {
  console.warn(
    `DATA DADDY: matchup data is Week ${publishedWeek}, ` +
    `but projections are Week ${displayWeek}. ` +
    "Suppressing mismatched matchup signals."
  );

  teamNextOpponent = {};
  defensePositionAllowed = {};
  currentPlayCallerSignals = {};
  currentTrenchSignals = {};
  currentScoringEnvironment = {};
  currentPlayerVsDefensiveCaller = {};
  trenchSignalWeek = null;
}


    
console.log(
  "DATA DADDY week control:",
  {
    publishedWeek,
    calendarWeek,
    displayWeek
  }
);

await loadGoalLineData();  
await loadWeightedRedZoneData();
    

currentPlayerVsDefensiveCaller =
  matchupWeekAligned
    ? (data.current_player_vs_defensive_caller || {})
    : {};

  
  console.log(
  `NFL stats loaded: ${data.season}, ${weeklyStats.length} rows`
);

console.log(
  "Defensive matchup teams:",
  Object.keys(defensePositionAllowed).length
);

console.log(
  "Next-opponent teams:",
  Object.keys(teamNextOpponent).length
);

console.log(
  "Current play-caller signal teams:",
  Object.keys(currentPlayCallerSignals).length
);

console.log(
  "Current player-vs-defensive-caller signals:",
  Object.keys(currentPlayerVsDefensiveCaller).length
);

} catch (error) {
  console.error("Local NFL stats error:", error);
  weeklyStats = [];
}
}
async function loadVerifiedInjuryOuts() {
  verifiedInjuryOutKeys = new Set();
  verifiedInjuryOutIds = new Set();
  const week = Number(document.documentElement.dataset.targetWeek);
  if (!Number.isInteger(week)) return;
  try {
    const response = await fetch("./data/verified_injury_outs.json", {
      cache: "no-store"
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (payload.schema_version !== 1 || !Array.isArray(payload.out)) return;
    for (const item of payload.out) {
      if (item.season !== 2026 || item.week !== week || item.status !== "OUT") continue;
      verifiedInjuryOutIds.add(String(item.player_id));
      verifiedInjuryOutKeys.add(
        String(item.player_name).trim().toLowerCase() + "|" +
        String(item.team).trim().toUpperCase()
      );
    }
  } catch (error) {
    console.warn("Verified injury OUT feed unavailable:", error);
  }
}

async function loadWeeklyPprProjections() {
  const targetWeek = Number(
    document.documentElement.dataset.targetWeek
  );

  if (!Number.isFinite(targetWeek) || targetWeek <= 0) {
    console.warn(
      "PPR projections not loaded: target week is unavailable."
    );
    weeklyPprProjections = [];
    return;
  }

  const projectionFile =
    `./projection-model/2026-week${targetWeek}-ppr-projections.csv`;

  try {
    const response = await fetch(
      `${projectionFile}?v=1`,
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        `Could not load ${projectionFile}: ${response.status}`
      );
    }

    const csvText = await response.text();

    const lines = csvText
      .trim()
      .split(/\r?\n/);

    if (lines.length < 2) {
      throw new Error(
        "PPR projection CSV contains no player rows."
      );
    }

    function parseCsvLine(line) {
      const values = [];
      let current = "";
      let insideQuotes = false;

      for (let index = 0; index < line.length; index += 1) {
        const character = line[index];

        if (character === '"') {
          if (
            insideQuotes &&
            line[index + 1] === '"'
          ) {
            current += '"';
            index += 1;
          } else {
            insideQuotes = !insideQuotes;
          }

          continue;
        }

        if (
          character === "," &&
          !insideQuotes
        ) {
          values.push(current);
          current = "";
          continue;
        }

        current += character;
      }

      values.push(current);

      return values;
    }

    const headers =
      parseCsvLine(lines[0])
        .map(header => header.trim());

    const requiredColumns = [
      "snapshot_week",
      "player_id",
      "player_name",
      "position",
      "team",
      "projected_ppr",
      "projected_position_rank",
      "projection_model"
    ];

    const missingColumns =
      requiredColumns.filter(
        column => !headers.includes(column)
      );

    if (missingColumns.length > 0) {
      throw new Error(
        "PPR projection CSV is missing columns: " +
        missingColumns.join(", ")
      );
    }

    weeklyPprProjections =
      lines
        .slice(1)
        .filter(line => line.trim())
        .map((line) => {
          const values =
            parseCsvLine(line);

          const row = {};

          headers.forEach(
            (header, index) => {
              row[header] =
                values[index] ?? "";
            }
          );

          row.snapshot_week =
            Number(row.snapshot_week);

          row.projected_ppr =
            Number(row.projected_ppr);

          row.projected_position_rank =
            Number(
              row.projected_position_rank
            );

          row.model_score =
            Number(row.model_score);

          return row;
        })
        .filter(row => !verifiedInjuryOutIds.has(String(row.player_id)) && !verifiedInjuryOutKeys.has(
          String(row.player_name).trim().toLowerCase() + "|" +
          String(row.team).trim().toUpperCase()
        ));

    // Restore players dropped from the live feed after their games finish.
    // Preserve the archived pregame projection, opponent and rank exactly.
    if (targetWeek === 7) {
      try {
        const archivedResponse = await fetch(
          "./projection-model/2026-week7-ppr-archived-pregame.csv?v=1",
          { cache: "no-store" }
        );
        if (archivedResponse.ok) {
          const archivedLines = (await archivedResponse.text()).trim().split(/\r?\n/);
          const archivedHeaders = parseCsvLine(archivedLines[0]);
          const currentKeys = new Set(weeklyPprProjections.map(row =>
            [normalizeName(row.player_name), String(row.position).toUpperCase()].join("|")
          ));
          for (const line of archivedLines.slice(1)) {
            if (!line.trim()) continue;
            const values = parseCsvLine(line);
            const archived = {};
            archivedHeaders.forEach((header, index) => { archived[header] = values[index] ?? ""; });
            const key = [normalizeName(archived.player_name), String(archived.position).toUpperCase()].join("|");
            if (currentKeys.has(key)) continue;
            if (verifiedInjuryOutIds.has(String(archived.player_id)) ||
                verifiedInjuryOutKeys.has(String(archived.player_name).trim().toLowerCase() + "|" +
                  String(archived.team).trim().toUpperCase())) continue;
            archived.snapshot_week = Number(archived.snapshot_week);
            archived.projected_ppr = Number(archived.projected_ppr);
            archived.projected_position_rank = Number(archived.projected_position_rank);
            archived.model_score = Number(archived.model_score);
            archived.pregame_archived = true;
            weeklyPprProjections.push(archived);
            currentKeys.add(key);
          }
        }
      } catch (error) {
        console.warn("Archived pregame projections unavailable:", error);
      }
    }

    // Keep archived ranks unchanged: these are historical pregame predictions.
    // Current live ranks also remain as published; never renumber after results.


    pprProjectionByPlayerId.clear();
    pprProjectionByPlayerKey.clear();

    weeklyPprProjections.forEach(
      (projection) => {
        const playerId =
          String(
            projection.player_id || ""
          ).trim();

        if (playerId) {
          pprProjectionByPlayerId.set(
            playerId,
            projection
          );
        }

        const playerKey = [
          normalizeName(
            projection.player_name
          ),
          String(
            projection.position || ""
          ).toUpperCase()
        ].join("|");

        pprProjectionByPlayerKey.set(
          playerKey,
          projection
        );
      }
    );

    console.log(
      `Week ${targetWeek} PPR projections loaded:`,
      weeklyPprProjections.length
    );
  } catch (error) {
    console.error(
      "PPR projection loading error:",
      error
    );

    weeklyPprProjections = [];
    pprProjectionByPlayerId.clear();
    pprProjectionByPlayerKey.clear();
  }
}


function getPlayerPprProjection(player) {
  if (!player) {
    return null;
  }

  const ids = [
    player.nflId,
    player.id
  ]
    .filter(Boolean)
    .map(id => String(id));

  for (const id of ids) {
    const projection =
      pprProjectionByPlayerId.get(id);

    if (projection) {
      return projection;
    }
  }
  const playerKey = [
    normalizeName(player.name),
    String(
      player.position || ""
    ).toUpperCase()
  ].join("|");

  return (
    pprProjectionByPlayerKey.get(
      playerKey
    ) || null
  );
}  
const PROJECTIONS_PER_PAGE = 24;

let currentProjectionPage = 1;
let currentProjectionPosition = "ALL";


function getProjectionPlayer(projection) {
  if (!projection) {
    return null;
  }

  const projectionId =
    String(
      projection.player_id || ""
    ).trim();

  if (projectionId) {
    const idMatch =
      players.find((player) => {
        // An ID alone is insufficient when feeds use different ID
        // namespaces or a stale roster record. Require the same
        // position and team before trusting the identity match.
        const team = value =>
          ({ LA: "LAR", JAC: "JAX", WSH: "WAS" })[
            String(value || "").toUpperCase()
          ] || String(value || "").toUpperCase();
        return [
          player.nflId,
          player.id
        ]
          .filter(Boolean)
          .map(id => String(id))
          .includes(projectionId) &&
          String(player.position || "").toUpperCase() ===
            String(projection.position || "").toUpperCase() &&
          team(player.team) === team(projection.team);
      });

    if (idMatch) {
      return idMatch;
    }
  }

  const projectionName =
    normalizeName(
      projection.player_name
    );

  const projectionPosition =
    String(
      projection.position || ""
    ).toUpperCase();
  const normalizeTeam = team =>
    ({ LA: "LAR", JAC: "JAX", WSH: "WAS" })[
      String(team || "").toUpperCase()
    ] || String(team || "").toUpperCase();
  const projectionTeam = normalizeTeam(projection.team);

  return (
    players.find((player) => {
      return (
        normalizeName(player.name) === projectionName &&
        String(player.position || "").toUpperCase() === projectionPosition &&
        normalizeTeam(player.team) === projectionTeam
      );
    }) || null
  );
}
let currentSleeperPosition = "ALL";

const SLEEPER_ELITE_CUTOFFS = {
  QB: 10,
  RB: 18,
  WR: 24,
  TE: 10
};


// Week 7-only reviewed injury-opportunity eligibility; no automatic uplift.
// Roles are conditional and must be re-reviewed for subsequent weeks.
function hasReviewedInjurySleeperOpportunity(projection) {
  if (Number(projection.snapshot_week) !== 7 ||
      Number(projection.season || 2026) !== 2026 ||
      String(projection.position || "").toUpperCase() !== "RB") return false;
  const team = String(projection.team || "").toUpperCase();
  const name = normalizeName(projection.player_name || "");
  return (team === "HOU" && name === normalizeName("Woody Marks")) ||
         (team === "ARI" && name === normalizeName("Tyler Allgeier")) ||
         (team === "ARI" && (name === normalizeName("Bam Knight") ||
           name === normalizeName("Zonovan Knight")));
}

function getWeeklySleeperCandidates() {
  const candidates =
    weeklyPprProjections
      .map((projection) => {
        const player =
          getProjectionPlayer(
            projection
          );

        if (!player) {
          return null;
        }

        // Historical PPR rows are for prediction-vs-actual audits only.
        // Never reintroduce a player removed from the current live
        // projection pool as an actionable sleeper.
        if (projection.pregame_archived) {
          return null;
        }

        // Sleepers are actionable pregame recommendations, not a
        // postgame leaderboard. Keep completed players in Rankings
        // and Projections for accuracy evaluation, but not here.
        if (getActualPprForRanking(player) !== null) {
          return null;
        }

        const position =
          String(
            projection.position || ""
          ).toUpperCase();

        if (
          !["QB", "RB", "WR", "TE"]
            .includes(position)
        ) {
          return null;
        }

        // Practice-squad depth WRs without a demonstrated weekly role
        // must not be recommended solely on AI/PPR rank disagreement.
        if (
          position === "WR" &&
          String(projection.team || "").toUpperCase() === "JAX" &&
          ["Austin Trammell", "Tim Jones"].includes(
            String(projection.player_name || player.player_name || player.name || "").trim()
          )
        ) {
          return null;
        }

        // WR sleepers need real current-season target opportunity.
        // Rank disagreement alone cannot promote depth receivers.
        // Use the most recent three recorded player-games; require
        // at least two games and 3 targets per game on average.
        // Injury-created WR opportunities require a separate reviewed
        // exception backed by role evidence, not a guessed boost.
        if (position === "WR") {
          const recentWrGames = getPlayerWeeklyStats(player)
            .filter(game => Number(game.season) === 2026)
            .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
            .slice(0, 3);
          const totalWrTargets = recentWrGames.reduce(
            (sum, game) => sum + Number(game.targets || 0), 0
          );
          if (
            recentWrGames.length < 2 ||
            totalWrTargets / recentWrGames.length < 3
          ) {
            return null;
          }
        }

        // TE sleepers require a credible weekly receiving role.
        // Rank disagreement alone cannot qualify a low-volume TE.
        if (position === "TE") {
          const recentTeGames = getPlayerWeeklyStats(player)
            .filter(game => Number(game.season) === 2026)
            .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
            .slice(0, 3);
          const totalTargets = recentTeGames.reduce(
            (sum, game) => sum + Number(game.targets || 0), 0
          );
          if (
            recentTeGames.length < 2 ||
            totalTargets / recentTeGames.length < 3 ||
            Number(projection.projected_ppr) < 8
          ) {
            return null;
          }
        }

        const projectedPpr =
          Number(
            projection.projected_ppr
          );

        const pprRank =
          Number(
            projection
              .projected_position_rank
          );

        const aiData =
          getLineupPlayerAiData(
            projection
          );

        const aiScore =
          Number(aiData.score);

        const aiRank =
          Number(aiData.rank);

        if (
          !Number.isFinite(projectedPpr) ||
          !Number.isFinite(pprRank) ||
          !Number.isFinite(aiScore) ||
          !Number.isFinite(aiRank)
        ) {
          return null;
        }

        /*
         * Do not call obvious elite weekly
         * options sleepers.
         */
        const eliteCutoff =
          SLEEPER_ELITE_CUTOFFS[
            position
          ];

        if (
          Number.isFinite(eliteCutoff) &&
          pprRank <= eliteCutoff
        ) {
          return null;
        }

        const rankAdvantage =
          pprRank - aiRank;

        /*
         * A model-derived sleeper must be
         * ranked higher by the Model Score
         * than by the PPR projection model.
         *
         * Example:
         * Model RB26 vs PPR RB32 = +6
         * qualifies.
         *
         * Model RB45 vs PPR RB22 = -23
         * does not qualify.
         */
        const injuryOpportunityEligible =
          hasReviewedInjurySleeperOpportunity(projection);
        if (rankAdvantage <= 0 && !injuryOpportunityEligible) {
          return null;
        }

        return {
          injuryOpportunityEligible,
          projection,
          player,
          position,
          projectedPpr,
          pprRank,
          aiScore,
          aiRank,
          rankAdvantage
        };
      })
      .filter(Boolean);

  if (candidates.length === 0) {
    return [];
  }

  /*
   * Compare each candidate only with other
   * sleeper-eligible players at his position.
   *
   * This prevents raw QB/RB/WR/TE scoring
   * differences from distorting Sleeper Score.
   */
  const positionGroups = {
    QB: [],
    RB: [],
    WR: [],
    TE: []
  };

  candidates.forEach(
    candidate => {
      positionGroups[
        candidate.position
      ].push(candidate);
    }
  );

  Object.values(
    positionGroups
  ).forEach(
    group => {
      if (group.length === 0) {
        return;
      }

      const aiScores =
        group.map(
          candidate =>
            candidate.aiScore
        );

      const pprValues =
        group.map(
          candidate =>
            candidate.projectedPpr
        );

      const rankAdvantages =
        group.map(
          candidate =>
            Math.max(0, candidate.rankAdvantage)
        );

      const minAi =
        Math.min(...aiScores);

      const maxAi =
        Math.max(...aiScores);

      const minPpr =
        Math.min(...pprValues);

      const maxPpr =
        Math.max(...pprValues);

      const minRankAdvantage =
        Math.min(
          ...rankAdvantages
        );

      const maxRankAdvantage =
        Math.max(
          ...rankAdvantages
        );

      group.forEach(
        candidate => {
          const aiComponent =
            normalizeSleeperMetric(
              candidate.aiScore,
              minAi,
              maxAi
            );

          const pprComponent =
            normalizeSleeperMetric(
              candidate.projectedPpr,
              minPpr,
              maxPpr
            );

          const disagreementComponent =
            normalizeSleeperMetric(
              Math.max(0, candidate.rankAdvantage),
              minRankAdvantage,
              maxRankAdvantage
            );

          /*
           * Sleeper Score
           *
           * 45% AI conviction
           * 35% weekly PPR projection
           * 20% AI-vs-PPR rank disagreement
           *
           * This is a standalone model-derived
           * discovery score.
           */
          candidate.sleeperScore =
            (
              aiComponent * 0.45 +
              pprComponent * 0.35 +
              disagreementComponent *
                0.20
            ) * 100;
        }
      );
    }
  );

  return candidates
    .filter(
      candidate =>
        Number.isFinite(
          candidate.sleeperScore
        )
    )
    .sort(
      (a, b) =>
        b.sleeperScore -
        a.sleeperScore
    );
}


function normalizeSleeperMetric(
  value,
  minimum,
  maximum
) {
  if (
    !Number.isFinite(value) ||
    !Number.isFinite(minimum) ||
    !Number.isFinite(maximum)
  ) {
    return 0;
  }

  if (maximum === minimum) {
    return 0.5;
  }

  return Math.max(
    0,
    Math.min(
      1,
      (
        value - minimum
      ) /
      (
        maximum - minimum
      )
    )
  );
}


function getSleeperReason(
  sleeper
) {
  const {
    position,
    aiRank,
    pprRank,
    rankAdvantage,
    projectedPpr
  } = sleeper;

  if (rankAdvantage >= 10) {
    return (
      `The model ranks him ${position}${aiRank}, ` +
      `${rankAdvantage} spots ahead of his ` +
      `${position}${pprRank} PPR projection rank. ` +
      `That is one of the stronger model ` +
      `disagreements at the position this week.`
    );
  }

  if (rankAdvantage >= 5) {
    return (
      `His underlying model signals place him at ` +
      `${position}${aiRank}, ${rankAdvantage} spots ` +
      `ahead of his ${position}${pprRank} projected ` +
      `PPR rank, creating an under-the-radar ` +
      `weekly opportunity.`
    );
  }

  if (rankAdvantage > 0) {
    return (
      `The model is slightly more optimistic ` +
      `than the PPR model, ranking him ` +
      `${position}${aiRank} compared with ` +
      `${position}${pprRank} by projected PPR. ` +
      `He still carries ${projectedPpr.toFixed(2)} ` +
      `projected PPR this week.`
    );
  }

  return (
    `He remains outside the elite weekly tier, ` +
    `but his combination of AI Score and ` +
    `${projectedPpr.toFixed(2)} projected PPR ` +
    `gives him one of the stronger profiles ` +
    `among the remaining ${position} options.`
  );
}


// Conditional editorial role alerts. These are not confirmed game-day statuses.
function getRoleCompetitionWatch(projection) {
  if (!projection || String(projection.position).toUpperCase() !== "RB") {
    return null;
  }
  const name = normalizeName(projection.player_name || "");
  const team = String(projection.team || "").toUpperCase();
  // Week 7 only: documented opportunity created by confirmed starter absences.
  // This is editorial role context, NOT an automatic Sleeper Score uplift.
  // Sources: official team reporting and 2026 Week 7 injury statuses;
  // observed touches: projection-model/validation/injury-opportunity-candidates.csv.
  // Re-evaluate for Week 8; never carry these warnings into later weeks.
  const snapshotWeek = Number(projection.snapshot_week);
  const snapshotSeason = Number(projection.season || 2026);
  if (snapshotSeason === 2026 && snapshotWeek === 7) {
    if (team === "ARI" && name === normalizeName("Tyler Allgeier")) {
      return "Week 7 injury opportunity: Jeremiyah Love is ruled out. Allgeier led Arizona's backfield in Week 6 with 18 carries and 40 snaps, but Bam Knight earned 15 carries and 32 snaps. Expect a shared backfield, not a guaranteed feature workload. Reassess when Love returns.";
    }
    if (team === "ARI" && name === normalizeName("Bam Knight")) {
      return "Week 7 injury opportunity: Jeremiyah Love is ruled out again. Knight carried 15 times for 80 yards in Week 6, but Allgeier led 18-15 in carries and 40-32 in snaps. Knight's increased role is real but conditional on Love remaining out, and the workload is shared.";
    }
    if (team === "HOU" && name === normalizeName("Woody Marks")) {
      return "Week 7 injury opportunity: David Montgomery is ruled out again and Jawhar Jordan is injured. Marks led Houston's backfield last week with 15 carries and 3 targets, and is expected to handle most meaningful carries. This is a one-week role outlook, not a permanent workload projection.";
    }
  }
  if (name === normalizeName("Emanuel Wilson") && team === "SEA") {
    return "Conditional sleeper: If Seattle's competing running backs are active and share carries this week, Wilson's workload could decline and he may no longer qualify as a sleeper. Check game-day availability and backfield usage before starting him.";
  }
  if (name === normalizeName("Braelon Allen") && team === "NYJ") {
    return "Roster watch: If Breece Hall suits up and takes his usual share of the Jets backfield, Braelon Allen's carries, projected PPR and sleeper eligibility could change. Confirm Hall's game-day status and workload before making a lineup decision.";
  }
  return null;
}

function renderWeeklySleepers() {
  const grid =
    document.getElementById(
      "sleepersGrid"
    );

  if (!grid) {
    return;
  }

  const weekBadge =
    document.getElementById(
      "sleepersWeekBadge"
    );

  const allSleepers =
    getWeeklySleeperCandidates();

  const filteredSleepers =
    allSleepers.filter(
      sleeper =>
        currentSleeperPosition ===
          "ALL" ||
        sleeper.position ===
          currentSleeperPosition
    );

  /*
   * Top 10 overall or Top 10 within the
   * selected position.
   */
  // Preserve the ranked Top 10; append reviewed injury opportunities
  // as watchlist entries rather than falsely labeling them Top-10 scores.
  const topTenSleepers = filteredSleepers.slice(0, 10);
  const additionalInjuryWatch = filteredSleepers.filter(
    sleeper =>
      sleeper.injuryOpportunityEligible &&
      !topTenSleepers.includes(sleeper)
  );
  const sleepers = [...topTenSleepers, ...additionalInjuryWatch];

  const projectionWeek =
    weeklyPprProjections
      .map(
        projection =>
          Number(
            projection.snapshot_week
          )
      )
      .find(
        week =>
          Number.isFinite(week)
      );

  if (weekBadge) {
    weekBadge.textContent =
      Number.isFinite(
        projectionWeek
      )
        ? `WEEK ${projectionWeek}`
        : "WEEK —";
  }

  grid.innerHTML = "";

    if (sleepers.length === 0) {
    const empty =
      document.createElement("div");

    empty.className =
      "sleepers-loading";

    const projectionsUnavailable =
      weeklyPprProjections.length === 0;

    empty.textContent =
      projectionsUnavailable
        ? "Weekly sleepers will populate when this week's PPR projections are available."
        : "No qualifying sleepers found for this position.";

    if (
      weekBadge &&
      projectionsUnavailable
    ) {
      const targetWeek =
        Number(
          document.documentElement
            .dataset.targetWeek
        );

      weekBadge.textContent =
        Number.isFinite(targetWeek) &&
        targetWeek > 0
          ? `WEEK ${targetWeek} • UPDATING`
          : "NEXT WEEK • UPDATING";
    }

    grid.appendChild(empty);

    return;
  }

  sleepers.forEach(
    (sleeper, index) => {
      const {
        projection,
        player,
        position,
        projectedPpr,
        pprRank,
        aiScore,
        aiRank,
        rankAdvantage,
        sleeperScore
      } = sleeper;

      const card =
        document.createElement(
          "article"
        );

      card.className =
        "sleeper-card";

      
        // Use the opponent from the same weekly
        // snapshot as the Sleeper's projections.
        const opponent =
          String(projection.opponent || "").trim() ||
          "TBD";


      const status =
        player.injuryStatus ||
        "Available";

      const rankDifferenceText =
        rankAdvantage > 0
          ? `Model +${rankAdvantage} spots`
          : rankAdvantage < 0
            ? `PPR +${Math.abs(
                rankAdvantage
              )} spots`
            : "Ranks aligned";
      card.innerHTML = `
        <div class="sleeper-card-top">
          <div class="sleeper-number">
            ${index < topTenSleepers.length ? "#" + (index + 1) : "WATCH"}
          </div>

          <div class="sleeper-score">
            <span>
              SLEEPER SCORE
            </span>

            <strong>
              ${sleeperScore.toFixed(1)}
            </strong>
          </div>
        </div>

        <div class="sleeper-player-heading">
          <div>
            <span class="sleeper-position">
              ${position}
            </span>

            <h3>
              ${projection.player_name}
            </h3>

            <p>
              ${projection.team || "—"}
              • vs ${opponent}
              • ${status}
            </p>
          </div>
        </div>

        <div class="sleeper-metrics">
          <div>
            <span>
              AI SCORE
            </span>

            <strong>
              ${aiScore.toFixed(1)}
            </strong>

            <small>
              ${position}${aiRank}
            </small>
          </div>

          <div>
            <span>
              PROJECTED PPR
            </span>

            <strong>
              ${projectedPpr.toFixed(2)}
            </strong>

            <small>
              ${position}${pprRank}
            </small>
          </div>

          <div>
            <span>
              MODEL SCORE VS PPR
            </span>
            <strong>
              ${
                rankAdvantage > 0
                  ? `+${rankAdvantage}`
                  : rankAdvantage
              }
            </strong>

            <small>
              ${rankDifferenceText}
            </small>
          </div>
        </div>

        <div class="sleeper-reason">
          <span>
            WHY THE MODEL LIKES HIM
          </span>

          <p>
            ${getSleeperReason(
              sleeper
            )}
          </p>
        </div>
      `;

      const roleWatch = getRoleCompetitionWatch(projection);
      if (roleWatch) {
        const warning = document.createElement("div");
        warning.className = "sleeper-reason";
        warning.style.borderLeft = "3px solid #d6a23a";
        warning.style.paddingLeft = "12px";
        const heading = document.createElement("strong");
        heading.textContent = "ROLE COMPETITION WATCH";
        const details = document.createElement("p");
        details.textContent = roleWatch;
        warning.append(heading, details);
        card.appendChild(warning);
      }

      grid.appendChild(card);
    }
  );
}

async function loadWaiverWire() {
  const container = document.getElementById("waiverWireList");
  const weekBadge = document.getElementById("waiverWeekBadge");

  if (!container) {
    return;
  }

  const showMessage = (message) => {
    container.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.textContent = message;
    container.appendChild(paragraph);
  };

  try {
    const response = await fetch(
      "./waiver_wire_candidates.json",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        `Waiver data request failed: ${response.status}`
      );
    }

    const data = await response.json();
    const candidates = Array.isArray(data.candidates)
      ? data.candidates
      : [];

    if (weekBadge) {
      const week = Number(data.target_week);
      weekBadge.textContent =
        Number.isInteger(week) && week > 0
          ? `WEEK ${week}`
          : "WEEK —";
    }

    
    const eligible = candidates.filter((player) => {
      return (
        player.ownership_eligible === true &&
        Number.isFinite(Number(player.average_rostered)) &&
        Number(player.average_rostered) < 65 &&
        player.injury_screening !== "flagged_unavailable"
      );
    });

    const provisional = Array.isArray(data.provisional_top_10)
      ? data.provisional_top_10
      : [];

    // Week 8 approved editorial waiver order; independent of model weights.
    // Deliberately render all approved names even if the automated candidate
    // pool omits a player. This prevents refreshes from silently reordering picks.
    if (Number(data.target_week) === 8) {
      const editorial = {
        overall: ["Omar Cooper Jr.","Tre Tucker","Jonah Coleman","Keon Coleman","KC Concepcion","Caleb Douglas","Hunter Henry","Chig Okonkwo","Antonio Williams","Tyler Higbee"],
        QB: ["Kirk Cousins","Jacoby Brissett","Malik Willis","Geno Smith","Aaron Rodgers"],
        RB: ["Jonah Coleman","Elijah Mitchell","Seth McGowan","Kaelon Black","Mike Washington Jr."],
        WR: ["Omar Cooper Jr.","Tre Tucker","Keon Coleman","KC Concepcion","Caleb Douglas"],
        TE: ["Hunter Henry","Chig Okonkwo","Tyler Higbee","Colby Parkinson","Brenton Strange"]
      };
      const teamFallback = {
        "Omar Cooper Jr.":"NYJ","Tre Tucker":"LV","Jonah Coleman":"DEN",
        "Keon Coleman":"BUF","KC Concepcion":"CLE","Caleb Douglas":"MIA",
        "Hunter Henry":"NE","Chig Okonkwo":"WAS","Antonio Williams":"WAS",
        "Tyler Higbee":"LAR","Kirk Cousins":"LV","Jacoby Brissett":"ARI",
        "Malik Willis":"MIA","Geno Smith":"NYJ","Aaron Rodgers":"PIT",
        "Elijah Mitchell":"PHI","Seth McGowan":"IND","Kaelon Black":"SF",
        "Mike Washington Jr.":"LV","Colby Parkinson":"LAR","Brenton Strange":"JAX"
      };
      // Editorial roster-watch notes: conditional roles, not injury confirmations.
      // Keep rankings stable while clearly separating pickups from start decisions.
      const rosterWatch = {
        "Keon Coleman": "Monitor DJ Moore’s availability. Coleman’s expanded opportunity depends on Moore being ruled out or limited.",
        "Elijah Mitchell": "Monitor Eagles RB injuries, game-day elevation and active status before relying on an expanded role.",
        "Seth McGowan": "ROSTER WATCH: Potential role expansion if Jonathan Taylor is traded. Monitor trade developments; no trade is assumed.",
        "Kaelon Black": "Monitor the RB depth chart and starter availability. Week 8 bye: stash only.",
        "Mike Washington Jr.": "Monitor Ashton Jeanty's availability. A meaningful workload boost depends on Jeanty being out or limited."
      };
      const positions = Object.fromEntries(
        ["QB","RB","WR","TE"].flatMap(pos => editorial[pos].map(name => [name,pos]))
      );
      positions["Antonio Williams"] = "WR";
      container.replaceChildren();
      const title = document.createElement("h3");
      title.textContent = "DATA DADDY — WEEK 8 WAIVER WIRE";
      container.appendChild(title);
      const description = document.createElement("p");
      description.textContent = "Official DATA DADDY editorial waiver priorities. AI projections and evidence scores are calculated independently. Monitor roster availability, injury reports and bye weeks.";
      container.appendChild(description);
      const sections = [
        ["TOP 10 OVERALL",editorial.overall],
        ["TOP 5 QUARTERBACKS",editorial.QB],
        ["TOP 5 RUNNING BACKS",editorial.RB],
        ["TOP 5 WIDE RECEIVERS",editorial.WR],
        ["TOP 5 TIGHT ENDS",editorial.TE]
      ];
      sections.forEach(([label,names]) => {
        const section = document.createElement("section");
        section.className = "waiver-editorial-section";
        const heading = document.createElement("h4");
        heading.textContent = label;
        section.appendChild(heading);
        names.forEach((name,index) => {
          const candidate = candidates.find(p => normalizeName(p.name) === normalizeName(name));
          const row = document.createElement("div");
          row.className = "waiver-player";
          const heading = document.createElement("strong");
          heading.textContent = "#" + (index+1) + " " + name + " (" + positions[name] + " • " + (candidate?.team || teamFallback[name] || "Team pending") + ")";
          row.appendChild(heading);
          if (rosterWatch[name]) {
            const watch = document.createElement("p");
            watch.className = "sleeper-reason waiver-roster-watch";
            watch.style.borderLeft = "3px solid #e3ae32";
            watch.style.padding = "6px 10px";
            watch.style.margin = "8px 0";
            const tag = document.createElement("strong");
            tag.textContent = "⚠ ROSTER WATCH — ";
            watch.appendChild(tag);
            watch.appendChild(document.createTextNode(rosterWatch[name]));
            row.appendChild(watch);
          }
          if (candidate) {
            const info = document.createElement("p");
            const score = Number(candidate.waiver_evidence_score);
            info.textContent = "Data Daddy evidence: " + (Number.isFinite(score) ? score.toFixed(2) + "/100" : "Not scored") +
              " • Rostered: " + (Number.isFinite(Number(candidate.average_rostered)) && candidate.average_rostered !== null ? Number(candidate.average_rostered).toFixed(1) + "%" : "Not verified");
            row.appendChild(info);
          } else {
            const info = document.createElement("p");
            info.textContent = "Editorial selection • Automated evidence/ownership pending verification";
            row.appendChild(info);
          }
          if (["Kaelon Black"].includes(name)) {
            const note = document.createElement("p");
            note.textContent = "Week 8 BYE — future-value stash";
            row.appendChild(note);
          }
          section.appendChild(row);
        });
        container.appendChild(section);
      });
      return;
    }

    // Week 7 editorial waiver rankings. Evidence scores remain model-generated.
    const editorialWeek7 = {
      overall: ["Germie Bernard","Omar Cooper Jr.","Kendre Miller","Ryan Flournoy","DeMario Douglas","Roschon Johnson","Tyler Higbee","Michael Mayer","Aaron Rodgers","Bam Knight"],
      QB: ["Aaron Rodgers","C.J. Stroud","Sam Darnold","Jalon Daniels","Tyler Huntley"],
      RB: ["Kendre Miller","Roschon Johnson","Bam Knight","Tyler Allgeier","Samaje Perine"],
      WR: ["Germie Bernard","Omar Cooper Jr.","Keenan Allen","DeMario Douglas","Ryan Flournoy"],
      TE: ["Tyler Higbee","Michael Mayer","Colby Parkinson","Chig Okonkwo","Darnell Washington"]
    };
    if (Number(data.target_week) === 7) {
      container.replaceChildren();
      const heading = document.createElement("h3");
      heading.textContent = "DATA DADDY — WEEK 7 WAIVER WIRE RANKINGS";
      container.appendChild(heading);
      const intro = document.createElement("p");
      intro.textContent = "Editorial waiver pickup priorities, not projected fantasy points. Data Daddy evidence scores are unmodified and may not be directly comparable across positions. Injury-dependent roles and unscored players are marked.";
      container.appendChild(intro);
      const renderRanking = (title, names) => {
        const section = document.createElement("section");
        section.className = "waiver-editorial-section";
        const label = document.createElement("h4");
        label.textContent = title;
        section.appendChild(label);
        names.forEach((name, index) => {
          const player = candidates.find((entry) => entry.name === name);
          const item = document.createElement("div");
          item.className = "waiver-player";
          const header = document.createElement("strong");
          header.textContent = "#" + (index + 1) + " " + name + (player ? " (" + player.position + " • " + player.team + ")" : "");
          item.appendChild(header);
          const info = document.createElement("p");
          const score = player && Number.isFinite(Number(player.waiver_evidence_score))
            ? Number(player.waiver_evidence_score).toFixed(2) + "/100"
            : "Not scored / eligibility pending";
          let note = "";
          if (name === "Bam Knight" || name === "Tyler Allgeier") note = " • Opportunity depends on Jeremiyah Love's availability";
          if (name === "Tyler Higbee") note = " • Editorial injury-opportunity selection; verify eligibility and role";
          if (name === "C.J. Stroud" && !player) note = " • Editorial pick; evidence score and roster eligibility pending";
          if (name === "Jalon Daniels") note = " • WATCH ONLY: Consider if Baker Mayfield is out AND Daniels is confirmed to start";
          if (name === "Tyler Huntley") note = " • WATCH ONLY: Consider if Lamar Jackson is out AND Huntley is confirmed to start";
          info.textContent = "Data Daddy Evidence Score: " + score + note;
          item.appendChild(info);
          const rostered = document.createElement("p");
          const rosterPct = player && Number.isFinite(Number(player.average_rostered))
            ? Number(player.average_rostered)
            : null;
          const sourceNames = player && player.ownership_sources && typeof player.ownership_sources === "object"
            ? Object.keys(player.ownership_sources).filter((source) =>
                Number.isFinite(Number(player.ownership_sources[source]?.percent)))
            : [];
          rostered.textContent = rosterPct !== null && sourceNames.length > 0
            ? "Rostered: " + rosterPct.toFixed(2) + "% (" + sourceNames.map((source) => source.toUpperCase()).join(", ") + ")"
            : "Rostered: Not verified";
          item.appendChild(rostered);
          // Display the verified target-week opponent and defensive matchup
          // already computed by the waiver builder. Never substitute 50 for
          // missing scores or display a matchup from a different week.
          const matchup = document.createElement("p");
          const matchupWeek = Number(player?.matchup_week);
          const opponent = player?.next_opponent;
          const location = player?.matchup_location;
          const matchupData = player?.defensive_matchup;
          const validWeek = matchupWeek === Number(data.target_week);
          if (validWeek && opponent) {
            const matchupText = location === "home" ? "vs " + opponent :
              location === "away" ? "@ " + opponent : "against " + opponent;
            const matchupScore = matchupData?.score;
            const validScore = matchupData?.opponent === opponent &&
              matchupData?.position === player.position &&
              matchupScore !== null && matchupScore !== undefined &&
              Number.isFinite(Number(matchupScore));
            matchup.textContent = "Week " + matchupWeek + " matchup: " +
              matchupText + " • Matchup Score: " +
              (validScore ? Number(matchupScore).toFixed(0) + "/100" : "Not available");
            const allowed = matchupData?.fantasy_points_allowed;
            if (validScore && allowed !== null && allowed !== undefined &&
                Number.isFinite(Number(allowed))) {
              matchup.textContent += " • Defense allows " +
                Number(allowed).toFixed(1) + " PPR/game to " + player.position;
            }
          } else {
            // An absent opponent is a BYE only when the schedule explicitly
            // identifies this team as off that week.
            const byeTeamsByWeek = {
              5: ["CAR", "KC"],
              6: ["CIN", "DET", "MIA", "MIN"],
              7: ["BUF", "JAX", "LAC", "WAS"],
              8: ["HOU", "NO", "NYG", "SF"],
              9: ["PIT", "TEN"],
              10: ["CHI", "DEN", "PHI", "TB"],
              11: ["ATL", "CLE", "GB", "LAR", "NE", "SEA"],
              13: ["BAL", "IND", "LV", "NYJ"],
              14: ["ARI", "DAL"]
            };
            const playerTeam = String(player?.team || "").toUpperCase();
            const scheduledBye = (byeTeamsByWeek[Number(data.target_week)] || [])
              .includes(playerTeam);
            matchup.textContent = scheduledBye
              ? "Week " + data.target_week + " matchup: BYE"
              : "Week " + data.target_week +
                " matchup: Not verified • Matchup Score: Not available";
          }
          item.appendChild(matchup);
          // Reuse the AI Rankings weekly-stat feed for every editorial waiver player.
          // Show position-specific season totals and the latest completed game.
          const games = getPlayerWeeklyStats({ name })
            .filter((game) => Number(game.season) === Number(data.season)
              && Number(game.week) < Number(data.target_week))
            .sort((a, b) => Number(b.week || 0) - Number(a.week || 0));
          if (games.length > 0) {
            const total = (field) => games.reduce(
              (sum, game) => sum + (Number(game[field]) || 0), 0
            );
            const fmt = (number) => Number(number.toFixed(1)).toLocaleString("en-US");
            const position = player?.position ||
              players.find((entry) => normalizeName(entry.name) === normalizeName(name))?.position ||
              (editorialWeek7.QB.includes(name) ? "QB" :
                editorialWeek7.RB.includes(name) ? "RB" :
                editorialWeek7.WR.includes(name) ? "WR" : "TE");
            const stats = document.createElement("p");
            const latest = games[0];
            const latestLine = document.createElement("p");
            if (position === "QB") {
              const hasStat = (field) => games.some(
                (game) => game[field] !== undefined && game[field] !== null
              );
              const attemptsField = hasStat("attempts") ? "attempts" :
                hasStat("passing_attempts") ? "passing_attempts" : null;
              const completionsField = hasStat("completions") ? "completions" :
                hasStat("passing_completions") ? "passing_completions" : null;
              const interceptionsField = hasStat("interceptions") ? "interceptions" :
                hasStat("passing_interceptions") ? "passing_interceptions" : null;
              const passingParts = [];
              if (attemptsField && completionsField) {
                passingParts.push(fmt(total(completionsField)) + "/" + fmt(total(attemptsField)) + " completions");
              } else if (attemptsField) {
                passingParts.push(fmt(total(attemptsField)) + " attempts");
              }
              passingParts.push(fmt(total("passing_yards")) + " yards");
              passingParts.push(fmt(total("passing_tds")) + " TD");
              if (interceptionsField) {
                passingParts.push(fmt(total(interceptionsField)) + " INT");
              }
              stats.textContent = "2026 passing: " + passingParts.join(" • ");
              latestLine.textContent = "Week " + latest.week + ": " +
                fmt(Number(latest.passing_yards) || 0) + " pass yards • " +
                fmt(Number(latest.passing_tds) || 0) + " pass TD • " +
                fmt(Number(latest.rushing_yards) || 0) + " rush yards";
            } else if (position === "RB") {
              stats.textContent = "2026 rushing/receiving: " + fmt(total("carries")) +
                " carries • " + fmt(total("rushing_yards")) + " rush yards • " +
                fmt(total("rushing_tds")) + " rush TD • " + fmt(total("targets")) +
                " targets • " + fmt(total("receptions")) + " catches • " +
                fmt(total("receiving_yards")) + " rec yards";
              latestLine.textContent = "Week " + latest.week + ": " +
                fmt(Number(latest.carries) || 0) + " carries • " +
                fmt(Number(latest.rushing_yards) || 0) + " rush yards • " +
                fmt(Number(latest.targets) || 0) + " targets • " +
                fmt(Number(latest.receptions) || 0) + " catches";
            } else {
              stats.textContent = "2026 receiving: " + fmt(total("targets")) +
                " targets • " + fmt(total("receptions")) + " catches • " +
                fmt(total("receiving_yards")) + " yards • " +
                fmt(total("receiving_tds")) + " TD";
              latestLine.textContent = "Week " + latest.week + ": " +
                fmt(Number(latest.targets) || 0) + " targets • " +
                fmt(Number(latest.receptions) || 0) + " catches • " +
                fmt(Number(latest.receiving_yards) || 0) + " yards";
            }
            item.appendChild(stats);
            item.appendChild(latestLine);
          } else {
            const missingStats = document.createElement("p");
            missingStats.textContent = "2026 weekly production: no completed-game stats available";
            item.appendChild(missingStats);
          }
          section.appendChild(item);
        });
        container.appendChild(section);
      };
      renderRanking("OVERALL TOP 10", editorialWeek7.overall);
      ["QB","RB","WR","TE"].forEach((position) => renderRanking(position === "QB" ? "TOP 3 QB + 2 INJURY WATCH OPTIONS" : "TOP 5 " + position, editorialWeek7[position]));
      return;
    }

    if (provisional.length > 0) {
      container.replaceChildren();

    const notice = document.createElement("p");
      notice.textContent =
        `DATA DADDY — WEEK ${data.target_week} PRELIMINARY WAIVER WATCHLIST. ` +
        "These 10 players are selected using opportunity trends, " +
        "recent fantasy production, and verified available ownership data. " +
        "Players flagged as unavailable by ESPN are screened out. " +
        "Official injury clearance, starting roles, and matchups " +
        "have not yet been fully verified. " +
        "This watchlist is designed to update daily as new data becomes available.";

        container.appendChild(notice);

        if (data.last_updated) {
          const updated = document.createElement("p");
          updated.className = "waiver-last-updated";

          const updatedDate = new Date(data.last_updated);

          if (!Number.isNaN(updatedDate.getTime())) {
            updated.textContent =
              "LAST UPDATED: " +
              updatedDate.toLocaleString("en-US", {
                timeZone: "America/Los_Angeles",
                month: "long",
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
                timeZoneName: "short"
              });

            container.appendChild(updated);
          }
        }

        provisional.forEach((player) => {

        const fullPlayer = candidates.find(
          (candidate) => candidate.player_id === player.player_id
        ) || player;

        const teammateReports = Array.isArray(fullPlayer.teammate_injury_evidence)
          ? fullPlayer.teammate_injury_evidence
          : [];

        const relevantStatuses = new Set([
          "OUT",
          "DOUBTFUL",
          "QUESTIONABLE",
          "INJURY_RESERVE",
          "IR",
          "PUP",
          "GTD",
          "DAY_TO_DAY"
        ]);

        const injuredTeammates = teammateReports.filter((teammate) => {
          return relevantStatuses.has(
            String(teammate.espn_status || "").toUpperCase()
          );
        });

        const injurySummary = injuredTeammates
          .map((teammate) =>
            `${teammate.name} (${String(teammate.espn_status).replaceAll("_", " ")})`
          )
          .join("; ");

        const row = document.createElement("div");
        row.className = "waiver-player";

        const title = document.createElement("strong");
        title.textContent =
          `#${player.provisional_rank} ${player.name} ` +
          `(${player.position} • ${player.team})`;

        const details = document.createElement("p");
        const ownership = Number(player.average_rostered);
        const score = Number(player.waiver_evidence_score);
        
        const matchupWeek = Number(player.matchup_week ?? data.target_week);
        const nextOpponent = player.next_opponent;
        const matchupLocation = player.matchup_location;

        const matchupLabel = !nextOpponent
          ? "BYE / Schedule unavailable"
          : matchupLocation === "home"
            ? `vs ${nextOpponent}`
            : matchupLocation === "away"
              ? `@ ${nextOpponent}`
              : `Opponent: ${nextOpponent}`;

        const defensiveScore = player.defensive_matchup?.score;
        const defensivePpr = player.defensive_matchup?.fantasy_points_allowed;
        const defensiveSample = player.defensive_matchup?.sample_size_2026;
        const hasDefensiveMatchup =
          nextOpponent &&
          defensiveScore !== null &&
          defensiveScore !== undefined &&
          defensivePpr !== null &&
          defensivePpr !== undefined &&
          Number.isFinite(Number(defensiveScore)) &&
          Number.isFinite(Number(defensivePpr));

        const defensiveLabel = hasDefensiveMatchup
          ? ` • Matchup: ${Number(defensiveScore).toFixed(0)}/100` +
            ` • Defense allows: ${Number(defensivePpr).toFixed(1)} PPR/game` +
            ` (${Number(defensiveSample) || 0} games)`
          : " • Defensive matchup: N/A";

        details.textContent =
          `Rostered: ${Number.isFinite(ownership) ? ownership.toFixed(1) + "%" : "Unverified"} (${Object.keys(fullPlayer.ownership_sources || {}).map(source => source.toUpperCase()).join(", ") || "source unverified"})` +
          `\nWaiver Evidence Score: ${Number.isFinite(score) ? score.toFixed(1) + "/100" : "—"}` +
          `\nScoring: 45% opportunity growth • 35% recent PPR • 20% current volume` +
          `\nInjury status: ${
            player.injury_feed_status
              ? String(player.injury_feed_status).replaceAll("_", " ")
              : "No ESPN injury designation reported"
          }` +

          `\nWeek ${matchupWeek}: ${matchupLabel}` +
          defensiveLabel;
        details.style.whiteSpace = "pre-line";
        
        const intelligence = document.createElement("div");
        intelligence.className = "waiver-intelligence";

        const heading = document.createElement("strong");
        heading.textContent = "DATA DADDY — PLAYER INTELLIGENCE";

        const usage = document.createElement("p");
        
        const history = player.role_usage_evidence?.usage_weekly_history;
        const latest = Array.isArray(history)
          ? history.find((game) => game.week === data.target_week - 1)
          : null;

        const carries = latest ? Number(latest.carries) : NaN;
        const targets = latest ? Number(latest.targets) : NaN;
        const attempts = latest ? Number(latest.pass_attempts) : NaN;


        const usageParts = [];

        if (Number.isFinite(carries) && carries > 0) {
          usageParts.push(`${carries} carries`);
        }
        if (Number.isFinite(targets) && targets > 0) {
          usageParts.push(`${targets} targets`);
        }
        if (Number.isFinite(attempts) && attempts > 0) {
          usageParts.push(`${attempts} pass attempts`);
        }

        usage.textContent = usageParts.length
          ? `RECENT USAGE: ${usageParts.join(" • ")}`
          : "RECENT USAGE: Detailed workload pending.";

        
        const assessment = document.createElement("p");

        const recentPpr = Number(fullPlayer.recent_average_ppr);
        const opportunityChange = Number(fullPlayer.opportunity_change);
        const recentAverages =
          player.role_usage_evidence?.usage_recent_3_game_averages || {};

        const metric = player.position === "QB"
          ? "pass_attempts"
          : player.position === "RB"
            ? "carries"
            : "targets";

        const metricLabel = metric === "pass_attempts"
          ? "pass attempts"
          : metric;

        const latestMetric = latest ? Number(latest[metric]) : NaN;
        const averageMetric = Number(recentAverages[metric]);

        let trendDescription = "Recent opportunity data is limited.";

        if (Number.isFinite(latestMetric) &&
            Number.isFinite(averageMetric)) {
          const difference = latestMetric - averageMetric;

          if (difference >= 2) {
            trendDescription =
              `Usage is trending upward: ${latestMetric} ${metricLabel} ` +
              `last week versus a three-game average of ` +
              `${averageMetric.toFixed(1)}.`;
          } else if (difference <= -2) {
            trendDescription =
              `Usage declined last week: ${latestMetric} ${metricLabel} ` +
              `versus a three-game average of ` +
              `${averageMetric.toFixed(1)}.`;
          } else {
            trendDescription =
              `Recent workload is relatively steady at ` +
              `${averageMetric.toFixed(1)} ${metricLabel} per game.`;
          }
        }

        const pprDescription = Number.isFinite(recentPpr)
          ? `Recent three-game average: ${recentPpr.toFixed(1)} PPR points.`
          : "Recent PPR production is unavailable.";

        const growthDescription = Number.isFinite(opportunityChange)
          ? `Model opportunity change: ${opportunityChange > 0 ? "+" : ""}${opportunityChange.toFixed(1)}.`
          : "Opportunity growth has not been measured.";

        
        const metrics = document.createElement("div");
        metrics.className = "waiver-metrics";

        const pprMetric = document.createElement("div");
        const growthMetric = document.createElement("div");

        const pprValue = Number.isFinite(recentPpr)
          ? recentPpr.toFixed(1)
          : "—";

        const growthValue = Number.isFinite(opportunityChange)
          ? `${opportunityChange > 0 ? "+" : ""}${opportunityChange.toFixed(1)}`
          : "—";

        
        pprMetric.textContent = `3-GAME AVG PPR: ${pprValue}`;
        growthMetric.textContent = `OPPORTUNITY CHANGE: ${growthValue}`;

        growthMetric.title =
          "Model-derived opportunity change across recent games. " +
          "This is separate from the position-specific workload comparison " +
          "shown in Opportunity Assessment below.";

        metrics.append(pprMetric, growthMetric);


        
        const positionOutlooks = {
          QB: "Passing volume creates opportunities for completions, yards, and touchdowns. Evaluate whether the offense can sustain this workload before treating him as a reliable starter.",
          RB: "Carries support rushing production, while targets can increase PPR value. A larger workload could improve his fantasy outlook if his role continues.",
          WR: "Targets create opportunities for receptions, yards, and touchdowns. Consistent target volume is important before relying on him as a weekly starter.",
          TE: "Targets are especially valuable when evaluating tight-end streaming options. Continued passing-game involvement could make him useful in PPR formats."
        };

        const positionOutlook =
          positionOutlooks[player.position] ||
          "Recent opportunities may create fantasy value, but future usage remains uncertain.";

        const workloadLabel = player.position === "QB"
          ? "pass attempts"
          : player.position === "RB"
            ? "carries"
            : "targets";

        const workload = Number.isFinite(latestMetric)
          ? `${latestMetric} ${workloadLabel} last week`
          : "limited recent workload data";

        const production = Number.isFinite(recentPpr)
          ? `averaging ${recentPpr.toFixed(1)} PPR points over the last three games`
          : "with recent fantasy production still being evaluated";

        const growth = Number.isFinite(opportunityChange)
          ? ` The model measures an opportunity change of ${opportunityChange > 0 ? "+" : ""}${opportunityChange.toFixed(1)}.`
          : "";

        const workloadIncrease =
          Number.isFinite(latestMetric) &&
          Number.isFinite(averageMetric)
            ? latestMetric - averageMetric
            : NaN;

        const playerValue =
          Number.isFinite(workloadIncrease) && workloadIncrease >= 2
            ? `${player.name} is a potential breakout waiver target because his recent workload is increasing. ` +
              (injuredTeammates.length > 0
                ? "Injuries at his position may create additional opportunities, but his future role is not confirmed."
                : "Consider adding him ahead of a possible larger role if you have roster flexibility.")
            : Number.isFinite(workloadIncrease) && workloadIncrease <= -2
              ? `${player.name} is a cautious waiver option because his recent workload has declined. ` +
                "Monitor for renewed involvement before relying on him."
              : Number.isFinite(recentPpr) && recentPpr > 0
                ? `${player.name} offers some recent fantasy production, but his role has not shown clear growth. ` +
                  "Consider him based on your roster needs rather than expecting an immediate breakout."
                : `${player.name} is a speculative waiver candidate. ` +
                  "Additional playing-time and production evidence is needed before making him a priority add.";
        const injuryContext = injuredTeammates.length > 0
          ? ` Same-position teammates with ESPN injury flags: ${injurySummary}. ` +
            "These statuses may affect future opportunity, but a direct replacement role is not verified."
          : "";

        const injuryOutlook = injuredTeammates.length > 0
          ? " Additional opportunities are possible if affected teammates miss time. " +
            "Their return timetables have not been verified."
          : "";

        const fantasyOutlook =
          player.position === "QB"
            ? "Passing volume offers fantasy upside, but scoring depends on efficiency, touchdowns, and continued playing time."
            : player.position === "RB"
              ? "A sustained rushing role can create fantasy value. Receiving opportunities may provide additional PPR upside."
              : player.position === "WR"
                ? "Consistent targets are important for reliable PPR production. Receiving efficiency and touchdown opportunities also matter."
                : player.position === "TE"
                  ? "A dependable passing-game role can create streaming value at tight end. Target consistency remains important."
                  : "Future fantasy value depends on continued opportunity and production.";

        assessment.textContent =
          `WHY ADD HIM?\n${playerValue}\n\n` +
          `FANTASY OUTLOOK:\n${fantasyOutlook} ` +
          "Future role and workload sustainability remain unverified.";
        assessment.style.whiteSpace = "pre-line";

        const opportunityOutlook = document.createElement("p");
        const usageDifference =
          Number.isFinite(latestMetric) && Number.isFinite(averageMetric)
            ? latestMetric - averageMetric
            : NaN;

        const usageTrend = Number.isFinite(usageDifference)
          ? usageDifference >= 2
            ? "RISING WORKLOAD"
            : usageDifference <= -2
              ? "DECLINING WORKLOAD"
              : "STABLE WORKLOAD"
          : "WORKLOAD UNVERIFIED";

        const usageEvidence = Number.isFinite(usageDifference)
          ? `${latestMetric} ${metricLabel} last week versus ${averageMetric.toFixed(1)} per game recently`
          : "Insufficient recorded workload to establish a trend";

        const fantasyEvidence = Number.isFinite(recentPpr)
          ? `${recentPpr.toFixed(1)} PPR points per game over the last three games`
          : "Recent fantasy production unavailable";

        const recommendation =
          usageTrend === "RISING WORKLOAD"
            ? "Potential breakout candidate if the increased role continues."
            : usageTrend === "DECLINING WORKLOAD"
              ? "Monitor for a workload rebound before relying on this player."
              : usageTrend === "STABLE WORKLOAD"
                ? "Current role appears relatively steady; watch for a new opportunity catalyst."
                : "More workload evidence is needed before assessing breakout potential.";

        opportunityOutlook.textContent =
          `OPPORTUNITY OUTLOOK — ${usageTrend}\n` +
          `${player.name}: ${usageEvidence}. ` +
          `Recent production: ${fantasyEvidence}. ` +
          recommendation;

        opportunityOutlook.style.whiteSpace = "pre-line";        

        opportunityOutlook.style.marginTop = "12px";
        opportunityOutlook.style.fontWeight = "600";
        opportunityOutlook.style.color = "#f5d37a";

        intelligence.append(
          heading,
          usage,
          metrics,
          assessment,
          opportunityOutlook
        );

        if (injuredTeammates.length > 0) {
          const injuryWatch = document.createElement("div");
          injuryWatch.className = "waiver-injury-watch";
          injuryWatch.style.marginTop = "16px";
          injuryWatch.style.whiteSpace = "pre-line";

          const injuryLines = injuredTeammates.map((teammate) => {
            const status = String(teammate.espn_status || "UNKNOWN")
              .replaceAll("_", " ");

            const averages = teammate.recent_usage?.usage_recent_3_game_averages || {};
            const sample = Number(teammate.recent_usage?.usage_sample_games);

            const metric = player.position === "QB"
              ? "pass_attempts"
              : player.position === "RB"
                ? "carries"
                : "targets";

            const metricLabel = metric === "pass_attempts"
              ? "pass attempts"
              : metric;

            const average = averages[metric];

            const workload = average !== null &&
              average !== undefined &&
              Number.isFinite(Number(average)) &&
              Number.isInteger(sample) &&
              sample > 0
                ? `${Number(average).toFixed(1)} ${metricLabel}/game (${sample} recorded games)`
                : "Recent workload unavailable";

            return `${teammate.name} — ${status}\nRecent workload: ${workload}`;
          });

          const injuryOpportunity =
            fullPlayer.injury_opportunity || player.injury_opportunity || {};

          const validLevels = new Set([
            "High",
            "Moderate",
            "Low",
            "Unverified"
          ]);

          const opportunityLevel = validLevels.has(injuryOpportunity.level)
            ? injuryOpportunity.level
            : "Unverified";

          const opportunityBasis = injuryOpportunity.basis;
          const basisMetric = injuryOpportunity.metric;

          const basisMetricLabel = basisMetric === "pass_attempts"
            ? "pass attempts"
            : basisMetric === "carries"
              ? "carries"
              : "targets";

          const hasValidBasis =
            opportunityBasis &&
            Number.isFinite(Number(opportunityBasis.average)) &&
            Number.isInteger(Number(opportunityBasis.sample_games)) &&
            Number(opportunityBasis.sample_games) >= 2 &&
            ["pass_attempts", "carries", "targets"].includes(basisMetric);

          const opportunityExplanation = hasValidBasis
            ? `${opportunityBasis.name}: ${Number(opportunityBasis.average).toFixed(1)} ${basisMetricLabel}/game across ${Number(opportunityBasis.sample_games)} recorded games.`
            : "Insufficient qualifying teammate workload evidence.";

          injuryWatch.textContent =
            "INJURY WATCH\n" +
            injuryLines.join("\n\n");

          const opportunitySection = document.createElement("div");
          opportunitySection.style.marginTop = "16px";
          opportunitySection.style.paddingTop = "12px";
          opportunitySection.style.borderTop = "1px solid rgba(255,255,255,0.15)";

          const opportunityHeading = document.createElement("div");
          opportunityHeading.style.display = "flex";
          opportunityHeading.style.alignItems = "center";
          opportunityHeading.style.flexWrap = "wrap";
          opportunityHeading.style.gap = "10px";

          const opportunityTitle = document.createElement("strong");
          opportunityTitle.textContent = "INJURY OPPORTUNITY SIGNAL";
          opportunityTitle.style.fontSize = "12px";
          opportunityTitle.style.letterSpacing = "0.5px";

          const opportunityBadge = document.createElement("span");
          opportunityBadge.textContent = opportunityLevel;
          opportunityBadge.style.fontSize = "12px";
          opportunityBadge.style.fontWeight = "700";
          opportunityBadge.style.padding = "4px 10px";
          opportunityBadge.style.borderRadius = "999px";

          const signalColors = {
            High: { background: "#194c39", color: "#a5f3c5" },
            Moderate: { background: "#574315", color: "#f5d37a" },
            Low: { background: "#203e59", color: "#a7d8ff" },
            Unverified: { background: "#3b414b", color: "#d0d5dd" }
          };

          const signalColor = signalColors[opportunityLevel];
          opportunityBadge.style.backgroundColor = signalColor.background;
          opportunityBadge.style.color = signalColor.color;

          opportunityHeading.append(opportunityTitle, opportunityBadge);

          const opportunityDetails = document.createElement("p");
          opportunityDetails.textContent = opportunityExplanation;
          opportunityDetails.style.margin = "10px 0";

          const opportunityNote = document.createElement("p");
          opportunityNote.textContent =
            "Historical teammate workload only. Replacement role, transferred " +
            "opportunities, and return timeline are not verified. " +
            "Injury statuses sourced from ESPN.";
          opportunityNote.style.fontSize = "12px";
          opportunityNote.style.opacity = "0.8";
          opportunityNote.style.margin = "8px 0 0";

          opportunitySection.append(
            opportunityHeading,
            opportunityDetails,
            opportunityNote
          );

          
          injuryWatch.appendChild(opportunitySection);
          intelligence.appendChild(injuryWatch);
        }

        // Separate opportunity assessment based on recorded usage.
        const opportunityAssessment = document.createElement("div");
        opportunityAssessment.className = "waiver-opportunity-assessment";
        opportunityAssessment.style.marginTop = "16px";
        opportunityAssessment.style.padding = "12px";
        opportunityAssessment.style.border = "1px solid rgba(212,175,55,0.35)";
        opportunityAssessment.style.borderRadius = "8px";
        opportunityAssessment.style.whiteSpace = "pre-line";

        
        const assessmentHeading = document.createElement("strong");
        assessmentHeading.textContent = "OPPORTUNITY ASSESSMENT";
        assessmentHeading.style.color = "#f5d37a";

        const assessmentDescription = document.createElement("p");
        assessmentDescription.textContent =
          "Compares the latest recorded game with previous games using " +
          "carries (RB), targets (WR/TE), or pass attempts (QB). " +
          "Separate from the model's Opportunity Change metric.";
        assessmentDescription.style.fontSize = "12px";
        assessmentDescription.style.opacity = "0.8";
        assessmentDescription.style.margin = "8px 0";


        
        const backendAssessment =
          fullPlayer.candidate_injury_opportunity_assessment ||
          player.candidate_injury_opportunity_assessment ||
          null;

        const assessmentLabels = {
          injury_flag_and_observed_usage_growth:
            "POTENTIAL OPPORTUNITY — INJURY FLAG + USAGE GROWTH",
          injury_flag_without_material_usage_growth:
            "INJURY FLAG — USAGE RELATIVELY STABLE",
          injury_flag_with_declining_usage:
            "INJURY FLAG — USAGE DECLINING",
          injury_flag_usage_trend_unverified:
            "INJURY FLAG — USAGE TREND UNVERIFIED",
          usage_growth_without_qualifying_injury_flag:
            "USAGE TRENDING UP",
          no_combined_injury_usage_signal:
            "NO COMBINED INJURY / USAGE SIGNAL"
        };

        const assessmentText = document.createElement("p");
        assessmentText.style.margin = "8px 0 0";

        if (backendAssessment) {
          const usageData = backendAssessment.candidate_usage || {};
          const assessmentLabel =
            assessmentLabels[backendAssessment.signal] ||
            "UNVERIFIED / MIXED EVIDENCE";

          const usageMetric = usageData.metric === "pass_attempts"
            ? "pass attempts"
            : usageData.metric === "carries"
              ? "carries"
              : usageData.metric === "targets"
                ? "targets"
                : "opportunities";

          const hasLatest =
            usageData.latest !== null &&
            usageData.latest !== undefined &&
            Number.isFinite(Number(usageData.latest));

          const hasBaseline =
            usageData.previous_average !== null &&
            usageData.previous_average !== undefined &&
            Number.isFinite(Number(usageData.previous_average));

          const hasChange =
            usageData.change !== null &&
            usageData.change !== undefined &&
            Number.isFinite(Number(usageData.change));

          const sample = Number(usageData.previous_sample_games);

          const usageExplanation = hasLatest && hasBaseline && hasChange
            ? `Latest recorded game: ${Number(usageData.latest).toFixed(1)} ${usageMetric}. ` +
              `Previous ${sample} recorded games: ` +
              `${Number(usageData.previous_average).toFixed(1)} ${usageMetric}/game. ` +
              `Change: ${Number(usageData.change) >= 0 ? "+" : ""}` +
              `${Number(usageData.change).toFixed(1)}.`
            : "Insufficient recorded workload evidence to establish a usage trend.";

          const flagged = Array.isArray(backendAssessment.flagged_teammates)
            ? backendAssessment.flagged_teammates
            : [];

          const injuryExplanation = flagged.length > 0
            ? `ESPN injury flags: ${flagged.map((teammate) =>
                `${teammate.name} (${String(teammate.espn_status || "UNKNOWN").replaceAll("_", " ")})`
              ).join("; ")}.`
            : "No qualifying teammate injury flag in this assessment.";

          assessmentText.textContent =
            `${assessmentLabel}\n` +
            `${usageExplanation}\n` +
            `${injuryExplanation}\n` +
            "Injury-related opportunity transfer, replacement role, " +
            "and future workload are not verified.";
        } else {
          assessmentText.textContent =
            "ASSESSMENT DATA UNAVAILABLE\n" +
            "The backend opportunity assessment is not available " +
            "for this player. No replacement role is inferred.";
        }
        
        opportunityAssessment.append(
          assessmentHeading,
          assessmentDescription,
          assessmentText
        );

        intelligence.appendChild(opportunityAssessment);

        row.append(title, details, intelligence);
        container.appendChild(row);


      });

      return;
    }

    
    if (eligible.length === 0) {
      showMessage(
        `${candidates.length} preliminary waiver candidates loaded. ` +
        "The official Top 10 is pending verified ESPN, Yahoo, " +
        "and Sleeper roster percentages and injury-opportunity data. " +
        "No unverified players will be published as recommendations."
      );
      return;
    }

    showMessage(
      `${eligible.length} candidates meet the preliminary ` +
      "ownership and injury-data requirements. " +
      "Final waiver scoring and ranking are still being prepared."
    );

  } catch (error) {
    console.error("Waiver Wire loading error:", error);

    if (weekBadge) {
      weekBadge.textContent = "WEEK —";
    }

    showMessage(
      "Waiver Wire data is temporarily unavailable. " +
      "Recommendations will appear when verified data is ready."
    );
  }
}


function renderProjectionBoard() {
  const tableBody =
    document.getElementById(
      "projectionTableBody"
    );

  const mobileCards =
    document.getElementById(
      "projectionMobileCards"
    );

  if (!tableBody) {
    return;
  }

  if (mobileCards) {
    mobileCards.innerHTML = "";
  }


  const searchInput =
    document.getElementById(
      "projectionSearch"
    );

  const searchTerm =
    String(
      searchInput?.value || ""
    )
      .trim()
      .toLowerCase();

  let projections =
    weeklyPprProjections
      .map((projection) => {
        return {
          projection,
          player:
            getProjectionPlayer(
              projection
            )
        };
      })
      .filter(({ projection }) => {
        const position =
          String(
            projection.position || ""
          ).toUpperCase();

        if (
          currentProjectionPosition !==
            "ALL" &&
          position !==
            currentProjectionPosition
        ) {
          return false;
        }

        if (!searchTerm) {
          return true;
        }

        const searchableText = [
          projection.player_name,
          projection.position,
          projection.team,
          projection.opponent
        ]
          .join(" ")
          .toLowerCase();

        return searchableText.includes(
          searchTerm
        );
      });

  /*
   * When ALL is selected, players are sorted
   * directly by projected PPR.
   *
   * When a position is selected, the existing
   * position-specific PPR rank controls order.
   */
  projections.sort((a, b) => {
    if (
      currentProjectionPosition === "ALL"
    ) {
      return (
        Number(
          b.projection.projected_ppr
        ) -
        Number(
          a.projection.projected_ppr
        )
      );
    }

    return (
      Number(
        a.projection
          .projected_position_rank
      ) -
      Number(
        b.projection
          .projected_position_rank
      )
    );
  });

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        projections.length /
          PROJECTIONS_PER_PAGE
      )
    );

  if (
    currentProjectionPage >
    totalPages
  ) {
    currentProjectionPage =
      totalPages;
  }

  const startIndex =
    (
      currentProjectionPage - 1
    ) * PROJECTIONS_PER_PAGE;

  const visibleProjections =
    projections.slice(
      startIndex,
      startIndex +
        PROJECTIONS_PER_PAGE
    );

  tableBody.innerHTML = "";

   if (
    visibleProjections.length === 0
  ) {
    const projectionsUnavailable =
      weeklyPprProjections.length === 0;

    tableBody.innerHTML = `
      <tr>
        <td colspan="10">
          ${
            projectionsUnavailable
              ? "Next week's projections are being prepared. Weekly PPR projections will appear here when the new matchup data is finalized."
              : "No projections match your current filters."
          }
        </td>
      </tr>
    `;

    const weekBadge =
      document.getElementById(
        "projectionWeekBadge"
      );

    if (
      weekBadge &&
      projectionsUnavailable
    ) {
      const targetWeek =
        Number(
          document.documentElement
            .dataset.targetWeek
        );

      weekBadge.textContent =
        Number.isFinite(targetWeek) &&
        targetWeek > 0
          ? `WEEK ${targetWeek} • UPDATING`
          : "NEXT WEEK • UPDATING";
    }

    renderProjectionPagination(
      1,
      1
    );

    return;
  }
  visibleProjections.forEach(
    ({ projection, player }) => {

      const position =
        String(
          projection.position || ""
        ).toUpperCase();

      const projectedRank =
        Number(
          projection
            .projected_position_rank
        );

      const projectedPpr =
        Number(
          projection.projected_ppr
        );

      // The Rankings and Projections tabs must use the same live
      // player, scoring profile and calculation. Never mix an older
      // projection snapshot's model_score with live AI Rankings.
      const profile = riskSelect?.value || "balanced";
      const aiScore = getProjectionAiScore(projection, player, profile);
      const aiRank = player
        ? getPlayerPositionRank(player, profile)
        : null;
      const jacobsWeek7 =
        projection.player_name === "Josh Jacobs" &&
        position === "RB" &&
        Number(projection.snapshot_week) === 7;


      
      // Use the opponent from the same weekly
      // projection snapshot as the PPR values.
      const opponent =
        String(projection.opponent || "").trim() ||
        "TBD";


      const status =
        player?.injuryStatus ||
        "Available";

      const actualPpr = player ? getActualPprForRanking(player) : null;
      const row =
        document.createElement("tr");

            const values = [
        Number.isFinite(projectedRank)
          ? `${position}${projectedRank}`
          : "—",

        projection.player_name || "Unknown",

        Number.isFinite(projectedPpr)
          ? projectedPpr.toFixed(2)
          : "—",

        position || "—",

        projection.team || "—",

        opponent,

        Number.isFinite(aiScore)
          ? aiScore.toFixed(1)
          : "—",

        aiRank
          ? `${position}${aiRank}`
          : "—",

        actualPpr === null ? "—" : actualPpr.toFixed(2),
        status
      ];

      const roleWatch = getRoleCompetitionWatch(projection);
      if (roleWatch) {
        const warningRow = document.createElement("tr");
        const warningCell = document.createElement("td");
        warningCell.colSpan = 10;
        warningCell.style.borderLeft = "3px solid #d6a23a";
        warningCell.style.padding = "8px 12px";
        warningCell.textContent = "ROLE COMPETITION WATCH — " + roleWatch;
        warningRow.appendChild(warningCell);
         // Insert directly after the matching player's row below.
        row._roleWatchRow = warningRow;
      }

      const jacobsExplanation = jacobsWeek7
        ? "Week 7 return-from-absence caution: his live AI Score reflects limited recent production, usage, and matchup signals. The separate 13.0 PPR projection is an editorial return-to-play estimate, not an AI Score."
        : "";

      values.forEach(
        (value, index) => {
          const cell =
            document.createElement("td");

          cell.textContent =
            String(value);
          if (jacobsExplanation && index === 6) {
            cell.title = jacobsExplanation;
            cell.style.textDecoration = "underline dotted";
            cell.style.cursor = "help";
          }
          row.appendChild(cell);
        }
      );

      tableBody.appendChild(row);
      if (row._roleWatchRow) {
        tableBody.appendChild(row._roleWatchRow);
      }

      if (mobileCards) {
        const card =
          document.createElement("article");

        card.className = "projection-mobile-card";

        const cardHeader =
          document.createElement("div");
        cardHeader.className = "projection-mobile-card-header";

        const playerName =
          document.createElement("strong");
        playerName.textContent =
          projection.player_name || "Unknown";

        const playerDetails =
          document.createElement("span");
        playerDetails.textContent =
          `${position} · ${projection.team || "—"} · vs ${opponent}`;

        cardHeader.append(playerName, playerDetails);

        const metrics =
          document.createElement("div");
        metrics.className = "projection-mobile-metrics";

        const metricValues = [
          ["Projected PPR", Number.isFinite(projectedPpr) ? projectedPpr.toFixed(2) : "—"],
          ["Actual PPR", actualPpr === null ? "—" : actualPpr.toFixed(2)],
          ["PPR Rank", Number.isFinite(projectedRank) ? `${position}${projectedRank}` : "—"],
          ["AI Rank", aiRank ? `${position}${aiRank}` : "—"],
          ["AI Score", Number.isFinite(aiScore) ? aiScore.toFixed(1) : "—"]
        ];

        metricValues.forEach(([label, value]) => {
          const metric = document.createElement("div");
          metric.className = "projection-mobile-metric";

          const labelElement = document.createElement("span");
          labelElement.textContent = label;

          const valueElement = document.createElement("strong");
          valueElement.textContent = value;

          metric.append(labelElement, valueElement);
          metrics.appendChild(metric);
        });

        const statusElement =
          document.createElement("div");
        statusElement.className = "projection-mobile-status";
        statusElement.textContent = `Status: ${status}`;

        card.append(cardHeader, metrics, statusElement);
        if (roleWatch) {
          const roleNotice = document.createElement("p");
          roleNotice.className = "projection-mobile-status";
          roleNotice.style.borderLeft = "3px solid #d6a23a";
          roleNotice.style.paddingLeft = "12px";
          roleNotice.textContent = "ROLE COMPETITION WATCH — " + roleWatch;
          card.appendChild(roleNotice);
        }
        if (jacobsExplanation) {
          const explanation = document.createElement("p");
          explanation.className = "projection-mobile-status";
          explanation.textContent = "Why his AI Score is low: " + jacobsExplanation;
          card.appendChild(explanation);
        }
        mobileCards.appendChild(card);
      }      
    }
  );

  renderProjectionPagination(
    currentProjectionPage,
    totalPages
  );

  const weekBadge =
    document.getElementById(
      "projectionWeekBadge"
    );

  if (weekBadge) {
    const weeks =
      weeklyPprProjections
        .map(
          projection =>
            Number(
              projection.snapshot_week
            )
        )
        .filter(
          week =>
            Number.isFinite(week)
        );

    const projectionWeek =
      weeks.length > 0
        ? weeks[0]
        : null;

    weekBadge.textContent =
      projectionWeek
        ? `WEEK ${projectionWeek}`
        : "WEEK —";
  }
}


function renderProjectionPagination(
  page,
  totalPages
) {
  const pagination =
    document.getElementById(
      "projectionPagination"
    );

  if (!pagination) {
    return;
  }

  pagination.innerHTML = "";

  if (totalPages <= 1) {
    return;
  }

  const previousButton =
    document.createElement("button");

  previousButton.type = "button";
  previousButton.textContent =
    "Previous";

  previousButton.disabled =
    page <= 1;

  previousButton.addEventListener(
    "click",
    () => {
      if (
        currentProjectionPage <= 1
      ) {
        return;
      }

      currentProjectionPage -= 1;
      renderProjectionBoard();
    }
  );

  const pageLabel =
    document.createElement("span");

  pageLabel.className =
    "ranking-page-status";

  pageLabel.textContent =
    `Page ${page} of ${totalPages}`;
  const nextButton =
    document.createElement("button");

  nextButton.type = "button";
  nextButton.textContent =
    "Next";

  nextButton.disabled =
    page >= totalPages;

  nextButton.addEventListener(
    "click",
    () => {
      if (
        currentProjectionPage >=
        totalPages
      ) {
        return;
      }

      currentProjectionPage += 1;
      renderProjectionBoard();
    }
  );

  pagination.append(
    previousButton,
    pageLabel,
    nextButton
  );
}  
const lineupRoster = [];
let lineupScreenshotFiles = [];


function setLineupRosterMethod(method) {
  const manualTab =
    document.getElementById(
      "manualRosterTab"
    );

  const screenshotTab =
    document.getElementById(
      "screenshotRosterTab"
    );

  const screenshotPanel =
    document.getElementById(
      "lineupScreenshotPanel"
    );

  const manualRosterBuilder =
    document.querySelector(
      ".lineup-roster-builder"
    );

  const useScreenshot =
    method === "screenshot";

  if (manualTab) {
    manualTab.classList.toggle(
      "active",
      !useScreenshot
    );
  }

  if (screenshotTab) {
    screenshotTab.classList.toggle(
      "active",
      useScreenshot
    );
  }

  if (screenshotPanel) {
    screenshotPanel.hidden =
      !useScreenshot;
  }

  if (manualRosterBuilder) {
    manualRosterBuilder.hidden =
      useScreenshot;
  }
}


function renderLineupScreenshotPreview() {
  const preview =
    document.getElementById(
      "lineupScreenshotPreview"
    );

  const status =
    document.getElementById(
      "lineupScreenshotStatus"
    );

  const detectedPlayers =
    document.getElementById(
      "lineupDetectedPlayers"
    );

  if (!preview) {
    return;
  }

  preview.innerHTML = "";

  if (!lineupScreenshotFiles.length) {
    preview.hidden = true;

    if (status) {
      status.textContent = "";
    }

    if (detectedPlayers) {
      detectedPlayers.hidden = true;
    }

    return;
  }

  lineupScreenshotFiles.forEach(
    (file) => {
      const item =
        document.createElement("div");

      item.className =
        "lineup-screenshot-preview-item";

      const image =
        document.createElement("img");

      image.alt =
        `Roster screenshot: ${file.name}`;

      const objectUrl =
        URL.createObjectURL(file);

      image.src = objectUrl;

      image.addEventListener(
        "load",
        () => {
          URL.revokeObjectURL(
            objectUrl
          );
        },
        { once: true }
      );

      const fileName =
        document.createElement("span");

      fileName.className =
        "lineup-screenshot-preview-name";

      fileName.textContent =
        file.name;

      item.append(
        image,
        fileName
      );

      preview.appendChild(item);
    }
  );

  preview.hidden = false;

  if (status) {
    const count =
      lineupScreenshotFiles.length;

    status.textContent =
      `${count} roster screenshot${
        count === 1 ? "" : "s"
      } ready for player detection.`;
  }

  if (detectedPlayers) {
    detectedPlayers.hidden = true;
  }
}


function handleLineupScreenshotSelection(
  event
) {
  const selectedFiles =
    Array.from(
      event.target.files || []
    ).filter(
      file =>
        file.type.startsWith(
          "image/"
        )
    );

  lineupScreenshotFiles =
    selectedFiles;

  renderLineupScreenshotPreview();
}
function getLineupProjectionKey(projection) {
  if (!projection) {
    return "";
  }

  const playerId =
    String(
      projection.player_id || ""
    ).trim();

  if (playerId) {
    return `id:${playerId}`;
  }

  return [
    "player",
    normalizeName(
      projection.player_name
    ),
    String(
      projection.position || ""
    ).toUpperCase()
  ].join(":");
}


function renderLineupPlayerResults() {
  const searchInput =
    document.getElementById(
      "lineupPlayerSearch"
    );

  const resultsContainer =
    document.getElementById(
      "lineupPlayerResults"
    );

  if (
    !searchInput ||
    !resultsContainer
  ) {
    return;
  }

  const searchTerm =
    String(searchInput.value || "")
      .trim()
      .toLowerCase();

  resultsContainer.innerHTML = "";

  if (searchTerm.length < 2) {
    return;
  }

  const rosterKeys =
    new Set(
      lineupRoster.map(
        getLineupProjectionKey
      )
    );

  const matches =
    weeklyPprProjections
      .filter((projection) => {
        const searchableText = [
          projection.player_name,
          projection.position,
          projection.team
        ]
          .join(" ")
          .toLowerCase();

        return (
          searchableText.includes(
            searchTerm
          ) &&
          !rosterKeys.has(
            getLineupProjectionKey(
              projection
            )
          )
        );
      })
      .sort((a, b) => {
        return (
          Number(b.projected_ppr) -
          Number(a.projected_ppr)
        );
      })
      .slice(0, 10);

  if (matches.length === 0) {
    const empty =
      document.createElement("div");

    empty.className =
      "lineup-empty-state";

    empty.textContent =
      "No matching projected players found.";

    resultsContainer.appendChild(
      empty
    );

    return;
  }

  matches.forEach((projection) => {
    const button =
      document.createElement("button");

    button.type = "button";
    button.className =
      "lineup-player-result";

    const playerInfo =
      document.createElement("span");

    const playerName =
      document.createElement("strong");

    const matchedPlayer =
      getProjectionPlayer(
        projection
      );

    playerName.textContent =
      projection.player_name ||
      matchedPlayer?.name ||
      "Unknown Player";
    const playerMeta =
      document.createElement("span");

    playerMeta.className =
      "lineup-player-result-meta";

    playerMeta.textContent =
      `${projection.position} • ` +
      `${projection.team || "—"}`;

    playerInfo.append(
      playerName,
      document.createElement("br"),
      playerMeta
    );

    const projectionValue =
      document.createElement("strong");

    const projectedPpr =
      Number(
        projection.projected_ppr
      );

    projectionValue.textContent =
      Number.isFinite(projectedPpr)
        ? `${projectedPpr.toFixed(2)} PPR`
        : "—";

    button.append(
      playerInfo,
      projectionValue
    );

    button.addEventListener(
      "click",
      () => {
        addPlayerToLineupRoster(
          projection
        );
      }
    );

    resultsContainer.appendChild(
      button
    );
  });
}


function addPlayerToLineupRoster(
  projection
) {
  if (!projection) {
    return;
  }

  const projectionKey =
    getLineupProjectionKey(
      projection
    );

  const alreadyAdded =
    lineupRoster.some(
      rosterPlayer =>
        getLineupProjectionKey(
          rosterPlayer
        ) === projectionKey
    );

  if (alreadyAdded) {
    return;
  }

  lineupRoster.push(projection);

  const searchInput =
    document.getElementById(
      "lineupPlayerSearch"
    );

  if (searchInput) {
    searchInput.value = "";
  }

  const resultsContainer =
    document.getElementById(
      "lineupPlayerResults"
    );

  if (resultsContainer) {
    resultsContainer.innerHTML = "";
  }

  renderLineupRoster();
}


function removePlayerFromLineupRoster(
  projectionKey
) {
  const playerIndex =
    lineupRoster.findIndex(
      projection =>
        getLineupProjectionKey(
          projection
        ) === projectionKey
    );

  if (playerIndex === -1) {
    return;
  }

  lineupRoster.splice(
    playerIndex,
    1
  );

  renderLineupRoster();
}


function renderLineupRoster() {
  const rosterContainer =
    document.getElementById(
      "lineupRoster"
    );

  const rosterCount =
    document.getElementById(
      "lineupRosterCount"
    );

  const optimizeButton =
    document.getElementById(
      "optimizeLineupBtn"
    );

  if (!rosterContainer) {
    return;
  }

  rosterContainer.innerHTML = "";

  if (rosterCount) {
    rosterCount.textContent =
      `${lineupRoster.length} ` +
      (
        lineupRoster.length === 1
          ? "player"
          : "players"
      );
  }

  if (optimizeButton) {
    optimizeButton.disabled =
      lineupRoster.length === 0;
  }

  if (lineupRoster.length === 0) {
    const emptyState =
      document.createElement("div");

    emptyState.className =
      "lineup-empty-state";

    emptyState.textContent =
      "Search for players above to build your fantasy roster.";

    rosterContainer.appendChild(
      emptyState
    );

    return;
  }

  const sortedRoster =
    [...lineupRoster].sort(
      (a, b) => {
        const positionOrder = {
          QB: 1,
          RB: 2,
          WR: 3,
          TE: 4
        };

        const aPosition =
          positionOrder[
            String(
              a.position || ""
            ).toUpperCase()
          ] || 99;

        const bPosition =
          positionOrder[
            String(
              b.position || ""
            ).toUpperCase()
          ] || 99;

        if (aPosition !== bPosition) {
          return aPosition - bPosition;
        }

        return (
          Number(b.projected_ppr) -
          Number(a.projected_ppr)
        );
      }
    );

  sortedRoster.forEach(
    (projection) => {
      const card =
        document.createElement("div");

      card.className =
        "lineup-roster-player";

      const info =
        document.createElement("div");

      info.className =
        "lineup-roster-player-info";

      const name =
        document.createElement("span");

      name.className =
        "lineup-roster-player-name";

      const matchedPlayer =
        getProjectionPlayer(
          projection
        );

      name.textContent =
        projection.player_name ||
        matchedPlayer?.name ||
        "Unknown Player";

      const meta =
        document.createElement("span");

      meta.className =
        "lineup-roster-player-meta";

      const projectedPpr =
        Number(
          projection.projected_ppr
        );

      meta.textContent =
        `${projection.position} • ` +
        `${projection.team || "—"} • ` +
        (
          Number.isFinite(
            projectedPpr
          )
            ? `${projectedPpr.toFixed(2)} PPR`
            : "—"
        );

      info.append(
        name,
        meta
      );

      const removeButton =
        document.createElement("button");

      removeButton.type = "button";
      removeButton.className =
        "lineup-remove-player";

      removeButton.setAttribute(
        "aria-label",
        `Remove ${projection.player_name}`
      );

      removeButton.textContent = "×";

      removeButton.addEventListener(
        "click",
        () => {
          removePlayerFromLineupRoster(
            getLineupProjectionKey(
              projection
            )
          );
        }
      );

      card.append(
        info,
        removeButton
      );

      rosterContainer.appendChild(
        card
      );
    }
  );
}


function clearLineupRoster() {
  lineupRoster.length = 0;

  const resultsContainer =
    document.getElementById(
      "lineupPlayerResults"
    );

  const searchInput =
    document.getElementById(
      "lineupPlayerSearch"
    );

  const result =
    document.getElementById(
      "lineupAnalyzerResult"
    );

  if (resultsContainer) {
    resultsContainer.innerHTML = "";
  }

  if (searchInput) {
    searchInput.value = "";
  }

  if (result) {
    result.innerHTML = "";
  }

  renderLineupRoster();
}


function updateLineupFormatControls() {
  const formatSelect =
    document.getElementById(
      "lineupFormat"
    );

  const customSettings =
    document.getElementById(
      "customLineupSettings"
    );

  if (
    !formatSelect ||
    !customSettings
  ) {
    return;
  }

  customSettings.hidden =
    formatSelect.value !== "custom";
}
function getLineupRules() {
  const formatSelect =
    document.getElementById(
      "lineupFormat"
    );

  const format =
    formatSelect?.value || "standard";

  const presets = {
    standard: {
      QB: 1,
      RB: 2,
      WR: 2,
      TE: 1,
      FLEX: 1,
      SUPERFLEX: 0
    },

    threeWR: {
      QB: 1,
      RB: 2,
      WR: 3,
      TE: 1,
      FLEX: 1,
      SUPERFLEX: 0
    },

    superflex: {
      QB: 1,
      RB: 2,
      WR: 2,
      TE: 1,
      FLEX: 1,
      SUPERFLEX: 1
    }
  };

  if (format !== "custom") {
    return presets[format] || presets.standard;
  }

  function readCount(id) {
    const input =
      document.getElementById(id);

    const value =
      Number(input?.value);

    if (!Number.isFinite(value)) {
      return 0;
    }

    return Math.max(
      0,
      Math.floor(value)
    );
  }

  return {
    QB: readCount("customQB"),
    RB: readCount("customRB"),
    WR: readCount("customWR"),
    TE: readCount("customTE"),
    FLEX: readCount("customFlex"),
    SUPERFLEX:
      readCount("customSuperflex")
  };
}

let nflInactiveObservations = null;

async function loadNflInactiveObservations() {
  try {
    const response = await fetch(
      "./data/nfl_inactive_observations.json",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(`NFL observations HTTP ${response.status}`);
    }

    const data = await response.json();

    if (
      data?.season !== 2026 ||
      data?.official_inactives_verified !== false ||
      !Array.isArray(data.games)
    ) {
      throw new Error("Invalid NFL observation feed");
    }

    nflInactiveObservations = data;

    console.log(
      "NFL.com game-specific observations loaded:",
      data.games.length,
      "games (unverified; informational only)"
    );
  } catch (error) {
    nflInactiveObservations = null;
    console.warn(
      "NFL.com observations unavailable:",
      error.message
    );
  }
}



let gamedayAvailability = null;

async function loadGamedayAvailability() {
  try {
    const response = await fetch(
      "./data/gameday_availability.json",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        `Availability snapshot HTTP ${response.status}`
      );
    }

    const snapshot = await response.json();

    if (
      !snapshot ||
      snapshot.season !== 2026 ||
      !snapshot.players ||
      typeof snapshot.players !== "object" ||
      !snapshot.generated_at_utc
    ) {
      throw new Error("Invalid availability snapshot");
    }

    const generatedAt = Date.parse(
      snapshot.generated_at_utc
    );

    const ageHours =
      (Date.now() - generatedAt) / 3600000;

    if (
      !Number.isFinite(ageHours) ||
      ageHours < -0.25 ||
      ageHours > 2
    ) {
      throw new Error(
        "Availability snapshot is stale or invalid"
      );
    }

    gamedayAvailability = snapshot;

    console.log(
      "Game-day availability loaded:",
      snapshot.player_count,
      "players; generated:",
      snapshot.generated_at_utc
    );
  } catch (error) {
    gamedayAvailability = null;
    console.warn(
      "Game-day availability unavailable:",
      error.message
    );
  }
}


function getLineupPlayersByPosition() {
  const groups = {
    QB: [],
    RB: [],
    WR: [],
    TE: []
  };

  const unavailableStatuses = new Set([
    "OUT",
    "IR",
    "INJURED_RESERVE",
    "INJURY_RESERVE",
    "PUP",
    "INACTIVE",
    "SUSPENDED",
    "EXEMPT",
    "EXEMPT_LIST",
    "RESERVE/EXEMPT",
    "RESERVE_EXEMPT"
  ]);

  lineupRoster.forEach((projection) => {
    const position = String(
      projection.position || ""
    ).toUpperCase();

    if (!groups[position]) {
      return;
    }

    const player = getProjectionPlayer(projection);

    const injuryStatus = String(
      player?.injuryStatus || ""
    ).trim().toUpperCase();

    
    const rosterStatus = String(
      player?.status || ""
    ).trim().toUpperCase();

    const sleeperId = String(
      player?.id || ""
    ).trim();

    const snapshotPlayer =
      gamedayAvailability?.players?.[sleeperId];

    const snapshotUnavailable =
      snapshotPlayer?.availability ===
      "unavailable_reported" &&
      String(snapshotPlayer.position || "").toUpperCase() === position &&
      String(snapshotPlayer.team || "").toUpperCase() ===
        String(player?.team || "").toUpperCase();

    if (
      unavailableStatuses.has(injuryStatus) ||
      unavailableStatuses.has(rosterStatus) ||
      snapshotUnavailable
    ) {
      return;
    }


    groups[position].push(projection);
  });

  Object.values(groups).forEach((positionPlayers) => {
    positionPlayers.sort(
      (a, b) =>
        Number(b.projected_ppr) -
        Number(a.projected_ppr)
    );
  });

  return groups;
}



function getLineupDistributions(
  count,
  positions
) {
  const distributions = [];

  function buildDistribution(
    index,
    remaining,
    current
  ) {
    if (
      index ===
      positions.length - 1
    ) {
      distributions.push({
        ...current,
        [positions[index]]:
          remaining
      });

      return;
    }

    const position =
      positions[index];

    for (
      let amount = 0;
      amount <= remaining;
      amount += 1
    ) {
      buildDistribution(
        index + 1,
        remaining - amount,
        {
          ...current,
          [position]: amount
        }
      );
    }
  }

  buildDistribution(
    0,
    count,
    {}
  );

  return distributions;
}


function findBestLegalLineup(
  rules,
  groups
) {
  const flexDistributions =
    getLineupDistributions(
      rules.FLEX,
      ["RB", "WR", "TE"]
    );

  const superflexDistributions =
    getLineupDistributions(
      rules.SUPERFLEX,
      ["QB", "RB", "WR", "TE"]
    );

  let bestLineup = null;

  flexDistributions.forEach(
    (flexAllocation) => {
      superflexDistributions.forEach(
        (superflexAllocation) => {
          const required = {
            QB:
              rules.QB +
              (
                superflexAllocation.QB ||
                0
              ),

            RB:
              rules.RB +
              (
                flexAllocation.RB ||
                0
              ) +
              (
                superflexAllocation.RB ||
                0
              ),

            WR:
              rules.WR +
              (
                flexAllocation.WR ||
                0
              ) +
              (
                superflexAllocation.WR ||
                0
              ),

            TE:
              rules.TE +
              (
                flexAllocation.TE ||
                0
              ) +
              (
                superflexAllocation.TE ||
                0
              )
          };

          const legal =
            Object.entries(
              required
            ).every(
              ([position, count]) =>
                groups[position].length >=
                count
            );

          if (!legal) {
            return;
          }

          const selected = {
            QB:
              groups.QB.slice(
                0,
                required.QB
              ),

            RB:
              groups.RB.slice(
                0,
                required.RB
              ),

            WR:
              groups.WR.slice(
                0,
                required.WR
              ),

            TE:
              groups.TE.slice(
                0,
                required.TE
              )
          };

          const starters =
            Object.values(
              selected
            ).flat();

          const total =
            starters.reduce(
              (sum, player) =>
                sum +
                Number(
                  player.projected_ppr ||
                  0
                ),
              0
            );

          if (
            !bestLineup ||
            total >
              bestLineup.total
          ) {
            bestLineup = {
              total,
              selected,
              flexAllocation,
              superflexAllocation
            };
          }
        }
      );
    }
  );

  return bestLineup;
}


function buildLineupSlots(
  lineup,
  rules
) {
  const slots = [];

  const remaining = {
    QB: [...lineup.selected.QB],
    RB: [...lineup.selected.RB],
    WR: [...lineup.selected.WR],
    TE: [...lineup.selected.TE]
  };

  function takePlayer(
    position,
    slotLabel
  ) {
    const player =
      remaining[position].shift();

    if (!player) {
      return;
    }

    slots.push({
      slot: slotLabel,
      player
    });
  }

  ["QB", "RB", "WR", "TE"].forEach(
    (position) => {
      for (
        let index = 0;
        index < rules[position];
        index += 1
      ) {
        takePlayer(
          position,
          position
        );
      }
    }
  );

  ["RB", "WR", "TE"].forEach(
    (position) => {
      const count =
        lineup.flexAllocation[
          position
        ] || 0;

      for (
        let index = 0;
        index < count;
        index += 1
      ) {
        takePlayer(
          position,
          "FLEX"
        );
      }
    }
  );

  ["QB", "RB", "WR", "TE"].forEach(
    (position) => {
      const count =
        lineup.superflexAllocation[
          position
        ] || 0;

      for (
        let index = 0;
        index < count;
        index += 1
      ) {
        takePlayer(
          position,
          "SUPERFLEX"
        );
      }
    }
  );

  return slots;
}


function getMissingLineupNeeds(
  rules,
  groups
) {
  const missing = [];

  ["QB", "RB", "WR", "TE"].forEach(
    (position) => {
      const required =
        rules[position];

      const available =
        groups[position].length;

      if (available < required) {
        missing.push(
          `${position}: need ${
            required - available
          } more`
        );
      }
    }
  );

  const baseRequired =
    rules.QB +
    rules.RB +
    rules.WR +
    rules.TE;

  const totalRequired =
    baseRequired +
    rules.FLEX +
    rules.SUPERFLEX;

  if (
    lineupRoster.length <
    totalRequired
  ) {
    missing.push(
      `Roster: need ${
        totalRequired -
        lineupRoster.length
      } more player${
        totalRequired -
          lineupRoster.length ===
        1
          ? ""
          : "s"
      }`
    );
  }

  return missing;
}

function getLineupPlayerAiData(projection) {
  if (!projection) {
    return { score: null, rank: null };
  }

  // AI Scores and ranks across Rankings, Projections, Sleepers and
  // Lineup Optimizer must come from the same live ranking source.
  // The projection CSV is authoritative only for projected PPR.
  const player = getProjectionPlayer(projection);
  if (!player) {
    return { score: null, rank: null };
  }
  const profile = riskSelect?.value || "balanced";
  const score = getDisplayedAiScore(player, profile);
  const rank = getPlayerPositionRank(player, profile);
  return {
    score: Number.isFinite(score) ? score : null,
    rank: Number.isInteger(rank) && rank > 0 ? rank : null
  };
}

function isPlayerEligibleForSlot(
  player,
  slot
) {
  const position =
    String(
      player.position || ""
    ).toUpperCase();

  if (
    ["QB", "RB", "WR", "TE"].includes(
      slot
    )
  ) {
    return position === slot;
  }

  if (slot === "FLEX") {
    return ["RB", "WR", "TE"].includes(
      position
    );
  }

  if (slot === "SUPERFLEX") {
    return [
      "QB",
      "RB",
      "WR",
      "TE"
    ].includes(position);
  }

  return false;
}


function getStartSitInsights(
  slots,
  bench
) {
  const insights = [];

  slots.forEach(
    ({ slot, player: starter }) => {
      const starterPpr =
        Number(
          starter.projected_ppr
        );

      const starterAi =
        getLineupPlayerAiData(
          starter
        );

      if (
        !Number.isFinite(starterPpr) ||
        !Number.isFinite(
          starterAi.score
        )
      ) {
        return;
      }

      
      bench.forEach(
        (benchPlayer) => {
          const eligiblePlayers =
            getLineupPlayersByPosition();

          const position = String(
            benchPlayer.position || ""
          ).toUpperCase();

          const isAvailable =
            (eligiblePlayers[position] || []).some(
              player =>
                getLineupProjectionKey(player) ===
                getLineupProjectionKey(benchPlayer)
            );

          if (
            !isAvailable ||
            !isPlayerEligibleForSlot(
              benchPlayer,
              slot
            )
          ) {
            return;
          }


          const benchPpr =
            Number(
              benchPlayer.projected_ppr
            );

          const benchAi =
            getLineupPlayerAiData(
              benchPlayer
            );

          if (
            !Number.isFinite(benchPpr) ||
            !Number.isFinite(
              benchAi.score
            )
          ) {
            return;
          }

          const projectionEdge =
            starterPpr - benchPpr;

          const aiEdge =
            benchAi.score -
            starterAi.score;

          if (
            projectionEdge < 0 ||
            projectionEdge > 3 ||
            aiEdge < 5
          ) {
            return;
          }

          insights.push({
            slot,
            starter,
            benchPlayer,
            starterPpr,
            benchPpr,
            starterAi,
            benchAi,
            projectionEdge,
            aiEdge
          });
        }
      );
    }
  );

  insights.sort(
    (a, b) => {
      if (
        b.aiEdge !== a.aiEdge
      ) {
        return (
          b.aiEdge - a.aiEdge
        );
      }

      return (
        a.projectionEdge -
        b.projectionEdge
      );
    }
  );

  const usedBenchPlayers =
    new Set();

  return insights
    .filter(
      insight => {
        const key =
          getLineupProjectionKey(
            insight.benchPlayer
          );

        if (
          usedBenchPlayers.has(key)
        ) {
          return false;
        }

        usedBenchPlayers.add(key);

        return true;
      }
    )
    .slice(0, 3);
}



function renderStartSitInsights(slots, bench) {
  const insights = getStartSitInsights(slots, bench);

  if (insights.length === 0) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "start-sit-insights";

  const heading = document.createElement("div");
  heading.className = "start-sit-insights-heading";

  const eyebrow = document.createElement("span");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "AI SECOND OPINION";

  const title = document.createElement("h4");
  title.textContent = "Start/Sit Insights";

  const intro = document.createElement("p");
  intro.textContent =
    "Projected PPR determines the optimal lineup. " +
    "These comparisons add matchup and opportunity " +
    "context to qualifying AI Score disagreements.";

  heading.append(eyebrow, title, intro);
  section.appendChild(heading);

  function getSignals(projection) {
    const player = getProjectionPlayer(projection);

    if (!player) {
      return null;
    }

    const position = String(
      player.position || projection.position || ""
    ).toUpperCase();

    const targetWeek = Number(
      document.documentElement.dataset.targetWeek
    );

    const games = getPlayerWeeklyStats(player)
      .filter(game =>
        Number(game.season) === 2026 &&
        Number(game.week) < targetWeek
      )
      .sort((a, b) =>
        Number(b.week) - Number(a.week)
      )
      .slice(0, 3);

    const matchup = teamNextOpponent[player.team];
    const defense =
      matchup?.opponent
        ? defensePositionAllowed[matchup.opponent]
        : null;

    const matchupAvailable =
      defense?.[position]?.fantasy_points_allowed != null;

    const matchupScore = matchupAvailable
      ? calculateMatchupScore(player)
      : null;

    const total = (field) =>
      games.reduce(
        (sum, game) => sum + Number(game[field] || 0),
        0
      );

    const average = (value) =>
      games.length > 0
        ? (value / games.length).toFixed(1)
        : null;

    let usageLabel = "Recent usage unavailable";
    let redZoneLabel = "Red-zone data unavailable";

    if (games.length > 0) {
      if (position === "RB") {
        usageLabel =
          `${average(total("carries"))} carries/game, ` +
          `${average(total("targets"))} targets/game`;

        redZoneLabel =
          `${average(total("red_zone_carries"))} ` +
          "red-zone carries/game";
      } else if (position === "WR" || position === "TE") {
        usageLabel =
          `${average(total("targets"))} targets/game`;

        redZoneLabel =
          `${average(total("red_zone_targets"))} ` +
          "red-zone targets/game";
      } else if (position === "QB") {
        usageLabel =
          `${average(total("attempts"))} pass attempts/game`;

        redZoneLabel =
          `${average(
            total("red_zone_pass_attempts") +
            total("red_zone_carries")
          )} red-zone opportunities/game`;
      }
    }

    return {
      games: games.length,
      usageLabel,
      redZoneLabel,
      matchupLabel: matchupAvailable
        ? `${matchup.opponent} • Matchup score ${matchupScore}/100`
        : "Matchup data unavailable"
    };
  }

  function addSignalRow(container, label, starterValue, benchValue) {
    const row = document.createElement("div");
    row.style.cssText =
      "display:grid;grid-template-columns:1fr 1fr;" +
      "gap:12px;padding:12px 0;" +
      "border-bottom:1px solid rgba(255,255,255,.12)";

    const left = document.createElement("div");
    const right = document.createElement("div");

    const leftLabel = document.createElement("small");
    leftLabel.textContent = `${label} — Starter`;

    const rightLabel = document.createElement("small");
    rightLabel.textContent = `${label} — Alternative`;

    const leftValue = document.createElement("div");
    leftValue.textContent = starterValue;

    const rightValue = document.createElement("div");
    rightValue.textContent = benchValue;

    left.append(leftLabel, leftValue);
    right.append(rightLabel, rightValue);
    row.append(left, right);
    container.appendChild(row);
  }

  insights.forEach(insight => {
    const card = document.createElement("div");
    card.className = "start-sit-insight-card";

    const starterName = insight.starter.player_name;
    const benchName = insight.benchPlayer.player_name;

    const cardTitle = document.createElement("h4");
    cardTitle.textContent =
      `${insight.slot}: ${starterName} vs. ${benchName}`;

    const summary = document.createElement("p");
    summary.textContent =
      `The PPR projection favors ${starterName} by ` +
      `${insight.projectionEdge.toFixed(2)} points, ` +
      `while AI Score favors ${benchName} by ` +
      `${insight.aiEdge.toFixed(1)} points.`;

    card.append(cardTitle, summary);

    addSignalRow(
      card,
      "Projected PPR",
      insight.starterPpr.toFixed(2),
      insight.benchPpr.toFixed(2)
    );

    addSignalRow(
      card,
      "AI Score",
      insight.starterAi.score.toFixed(1),
      insight.benchAi.score.toFixed(1)
    );

    const starterSignals = getSignals(insight.starter);
    const benchSignals = getSignals(insight.benchPlayer);

    addSignalRow(
      card,
      "Matchup",
      starterSignals?.matchupLabel || "Unavailable",
      benchSignals?.matchupLabel || "Unavailable"
    );

    addSignalRow(
      card,
      "Recent usage",
      starterSignals?.usageLabel || "Unavailable",
      benchSignals?.usageLabel || "Unavailable"
    );

    addSignalRow(
      card,
      "Red-zone opportunity",
      starterSignals?.redZoneLabel || "Unavailable",
      benchSignals?.redZoneLabel || "Unavailable"
    );

    
    const note = document.createElement("p");
    note.style.marginTop = "14px";

    const reasons = [];
    let starterSupport = 0;
    let benchSupport = 0;

    const starterMatchup =
      starterSignals?.matchupLabel || "";
    const benchMatchup =
      benchSignals?.matchupLabel || "";

    const starterMatchupScore = Number(
      starterMatchup.match(/Matchup score (\d+)/)?.[1]
    );
    const benchMatchupScore = Number(
      benchMatchup.match(/Matchup score (\d+)/)?.[1]
    );

    if (
      starterMatchup.includes("Matchup score") &&
      benchMatchup.includes("Matchup score")
    ) {
      const difference =
        benchMatchupScore - starterMatchupScore;

      if (difference >= 10) {
        benchSupport++;
        reasons.push(
          `${benchName} has the more favorable matchup.`
        );
      } else if (difference <= -10) {
        starterSupport++;
        reasons.push(
          `${starterName} has the more favorable matchup.`
        );
      }
    }

    const starterUsage = parseFloat(
      starterSignals?.usageLabel || ""
    );
    const benchUsage = parseFloat(
      benchSignals?.usageLabel || ""
    );

    if (
      insight.starter.position ===
        insight.benchPlayer.position &&
      Number.isFinite(starterUsage) &&
      Number.isFinite(benchUsage)
    ) {
      if (benchUsage >= starterUsage * 1.2 &&
          benchUsage - starterUsage >= 1) {
        benchSupport++;
        reasons.push(
          `${benchName} has greater recent opportunity volume.`
        );
      } else if (
        starterUsage >= benchUsage * 1.2 &&
        starterUsage - benchUsage >= 1
      ) {
        starterSupport++;
        reasons.push(
          `${starterName} has greater recent opportunity volume.`
        );
      }
    }

    const starterRedZone = parseFloat(
      starterSignals?.redZoneLabel || ""
    );
    const benchRedZone = parseFloat(
      benchSignals?.redZoneLabel || ""
    );

    if (
      insight.starter.position ===
        insight.benchPlayer.position &&
      Number.isFinite(starterRedZone) &&
      Number.isFinite(benchRedZone)
    ) {
      if (benchRedZone - starterRedZone >= 1) {
        benchSupport++;
        reasons.push(
          `${benchName} has more recent red-zone opportunities.`
        );
      } else if (starterRedZone - benchRedZone >= 1) {
        starterSupport++;
        reasons.push(
          `${starterName} has more recent red-zone opportunities.`
        );
      }
    }

    const recommendation =
      benchSupport >= 2 && benchSupport > starterSupport
        ? `Consider starting ${benchName} over ${starterName}.`
        : `Keep ${starterName} as the projected starter.`;

    note.textContent =
      `DATA DADDY Recommendation: ${recommendation} ` +
      `The PPR projection favors ${starterName} by ` +
      `${insight.projectionEdge.toFixed(2)} points, while ` +
      `AI Score favors ${benchName} by ` +
      `${insight.aiEdge.toFixed(1)} points. ` +
      (reasons.length
        ? reasons.join(" ")
        : "Available matchup and opportunity data do not " +
          "show a clear additional advantage.");

    card.appendChild(note);

    section.appendChild(card);
  });

  return section;
}


  
// Schedule is advisory only. The source schedule is not independently verified.
let lineupKickoffSchedule = null;
async function loadLineupKickoffSchedule() {
  lineupKickoffSchedule = null;
  try {
    const response = await fetch("./data/nfl_schedule_2026.json", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    if (data.season !== 2026 || !Array.isArray(data.games)) return;
    lineupKickoffSchedule = data.games;
  } catch (error) {
    console.warn("Lineup kickoff schedule unavailable:", error);
  }
}
function getLineupKickoff(projection) {
  const week = Number(document.documentElement.dataset.targetWeek);
  const team = String(projection.team || "").toUpperCase();
  if (!lineupKickoffSchedule || !Number.isInteger(week) || !team) return null;
  const matches = lineupKickoffSchedule.filter(game =>
    Number(game.week) === week &&
    [game.home_team, game.away_team].some(t =>
      String(t || "").toUpperCase() === team ||
      (team === "LAR" && t === "LA") ||
      (team === "JAX" && t === "JAC") ||
      (team === "WAS" && t === "WSH")
    )
  );
  if (matches.length !== 1) return null;
  const game = matches[0];
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(String(game.gameday)) ||
      !/^\\d{1,2}:\\d{2}$/.test(String(game.gametime))) return null;
  // Compare scheduled local Eastern kickoff labels, not guessed UTC offsets.
  return game.gameday + "T" + game.gametime.padStart(5, "0");
}
function currentEasternKickoffLabel() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit",
      day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(new Date()).map(p => [p.type, p.value])
  );
  return parts.year + "-" + parts.month + "-" + parts.day +
    "T" + parts.hour + ":" + parts.minute;
}

// Retrieval time only; Sleeper does not supply a verified report publication time.
let sleeperInjuryFetchedAt = null;

function renderLineupInjuryWatch(slots, bench) {
  const watch = [];
  for (const { slot, player: projection } of slots) {
    const player = getProjectionPlayer(projection);
    const status = String(player?.injuryStatus || "").trim().toUpperCase();
    if (!["QUESTIONABLE", "DOUBTFUL", "Q", "D"].includes(status)) continue;
    const alternatives = bench
      .filter(candidate => candidate.position === projection.position ||
        (slot.toUpperCase().includes("FLEX") && ["RB", "WR", "TE"].includes(candidate.position)))
      .filter(candidate => {
        const info = getProjectionPlayer(candidate);
        return !["QUESTIONABLE", "DOUBTFUL", "Q", "D"].includes(
          String(info?.injuryStatus || "").trim().toUpperCase()
        );
      })
      .sort((a, b) => Number(b.projected_ppr) - Number(a.projected_ppr));
    const starterKickoff = getLineupKickoff(projection);
    const nowEastern = currentEasternKickoffLabel();
    const lateOptions = starterKickoff && starterKickoff > nowEastern
      ? alternatives.filter(candidate => {
          const kickoff = getLineupKickoff(candidate);
          return kickoff && kickoff >= starterKickoff;
        })
      : [];
    watch.push({
      projection, status, alternative: alternatives[0],
      lateAlternative: lateOptions[0], starterKickoff
    });
  }
  if (!watch.length) return null;
  const section = document.createElement("section");
  section.className = "lineup-injury-watch";
  Object.assign(section.style, {
    border: "1px solid #c8a64d", borderRadius: "10px",
    padding: "14px 16px", margin: "16px 0"
  });
  const title = document.createElement("h4");
  title.textContent = "Injury Watch — Check Before Kickoff";
  section.appendChild(title);
  const note = document.createElement("p");
  note.textContent = "These starters have a reported injury designation. Status may change; verify the latest team inactive list before locking your lineup. Alternatives below are not guaranteed active.";
  section.appendChild(note);
  const freshness = document.createElement("p");
  const checkedAt = Number(sleeperInjuryFetchedAt);
  const elapsedMinutes = (Date.now() - checkedAt) / 60000;
  freshness.textContent = checkedAt > 0 && Number.isFinite(elapsedMinutes) && elapsedMinutes >= 0
    ? "Sleeper data retrieved " + Math.floor(elapsedMinutes) + " minute(s) ago. This is the retrieval time, not the injury report publication time."
    : "Sleeper injury report publication time unavailable. Check official game-day status before kickoff.";
  section.appendChild(freshness);
  for (const { projection, status, alternative, lateAlternative, starterKickoff } of watch) {
    const line = document.createElement("p");
    const name = document.createElement("strong");
    name.textContent = projection.player_name + " — " +
      (status === "Q" ? "QUESTIONABLE" : status === "D" ? "DOUBTFUL" : status);
    line.appendChild(name);
    if (alternative) {
      const gap = Number(projection.projected_ppr) - Number(alternative.projected_ppr);
      const detail = document.createElement("span");
      detail.textContent = " | Bench option: " + alternative.player_name +
        " (" + Number(alternative.projected_ppr).toFixed(2) + " PPR)" +
        (Number.isFinite(gap) ? "; projected difference: " + gap.toFixed(2) + " PPR" : "");
      line.appendChild(detail);
    } else {
      line.appendChild(document.createTextNode(" | No same-position bench alternative found."));
    }
    if (starterKickoff) {
      const swap = document.createElement("span");
      swap.textContent = lateAlternative
        ? " | Late-swap option: " + lateAlternative.player_name +
          " (scheduled kickoff no earlier than starter; " +
          Number(lateAlternative.projected_ppr).toFixed(2) + " PPR)"
        : " | No confirmed same-or-later kickoff bench option in this roster. Earlier backups may lock before the starter's status is known.";
      line.appendChild(swap);
    } else {
      line.appendChild(document.createTextNode(
        " | Kickoff comparison unavailable; verify bench game times."
      ));
    }
    section.appendChild(line);
  }
  return section;
}

function renderOptimizedLineup(
  lineup,
  rules,
  strategy = "best"
) {
  const result =
    document.getElementById(
      "lineupAnalyzerResult"
    );

  if (!result) {
    return;
  }

  result.innerHTML = "";

  const slots =
    buildLineupSlots(
      lineup,
      rules
    );

  const starterKeys =
    new Set(
      slots.map(({ player }) =>
        getLineupProjectionKey(
          player
        )
      )
    );

  const bench =
    lineupRoster
      .filter(
        player =>
          !starterKeys.has(
            getLineupProjectionKey(
              player
            )
          )
      )
      .sort(
        (a, b) =>
          Number(
            b.projected_ppr
          ) -
          Number(
            a.projected_ppr
          )
      );

  const heading =
    document.createElement("div");

  heading.className =
    "optimized-lineup-heading";

  heading.innerHTML = `
    <div>
      <span class="eyebrow">
        ${strategy === "safe" ? "SAFER LINEUP — INJURY DESIGNATIONS" : "BEST PROJECTED LINEUP"}
      </span>
      <h3>
        Optimal Starting Lineup
      </h3>
    </div>

    <div class="optimized-lineup-total">
      <span>Projected Total</span>
      <strong>
        ${lineup.total.toFixed(2)}
        PPR
      </strong>
    </div>
  `;

  result.appendChild(
    heading
  );

  const startersGrid =
    document.createElement("div");

  startersGrid.className =
    "optimized-lineup-grid";

  slots.forEach(
    ({ slot, player }) => {
      const card =
        document.createElement("div");

      card.className =
        "optimized-lineup-player";

      const projectedPpr =
        Number(
          player.projected_ppr
        );

      const aiData =
        getLineupPlayerAiData(
          player
        );

      const aiScoreText =
        Number.isFinite(
          aiData.score
        )
          ? aiData.score.toFixed(1)
          : "—";

      const aiRankText =
        aiData.rank
          ? `${player.position}${aiData.rank}`
          : "—";

      card.innerHTML = `
        <span class="optimized-lineup-slot">
          ${slot}
        </span>

        <div class="optimized-lineup-player-info">
          <strong>
            ${player.player_name}
          </strong>

          <span>
            ${player.position}
            •
            ${player.team || "—"}
          </span>

          <span class="optimized-lineup-ai">
  ${
    Number.isFinite(aiData.score)
      ? `AI Score ${aiScoreText} • ${aiRankText}`
      : "AI Score unavailable • Not currently ranked"
  }
</span>
        </div>

        <strong class="optimized-lineup-ppr">
          ${
            Number.isFinite(
              projectedPpr
            )
              ? projectedPpr.toFixed(2)
              : "—"
          }
          PPR
        </strong>
      `;

      startersGrid.appendChild(
        card
      );
    }
  );

  result.appendChild(
    startersGrid
  );

  const insightsSection =
    renderStartSitInsights(
      slots,
      bench
    );

  if (insightsSection) {
    result.appendChild(
      insightsSection
    );
  }

  const injuryWatch = renderLineupInjuryWatch(slots, bench);
  if (injuryWatch) result.appendChild(injuryWatch);

  if (bench.length > 0) {
    const benchHeading =
      document.createElement("h4");

    benchHeading.className =
      "optimized-bench-heading";

    benchHeading.textContent =
      "Bench";

    result.appendChild(
      benchHeading
    );

    const benchGrid =
      document.createElement("div");

    benchGrid.className =
      "optimized-bench-grid";

    bench.forEach(
      (player) => {
        const card =
          document.createElement(
            "div"
          );

        card.className =
          "optimized-bench-player";

        const projectedPpr =
          Number(
            player.projected_ppr
          );

        const aiData =
          getLineupPlayerAiData(
            player
          );

        const aiScoreText =
          Number.isFinite(
            aiData.score
          )
            ? aiData.score.toFixed(1)
            : "—";

        const aiRankText =
          aiData.rank
            ? `${player.position}${aiData.rank}`
            : "—";

        card.innerHTML = `
          <div>
            <strong>
              ${player.player_name}
            </strong>

             <span>
              ${player.position}
              •
              ${player.team || "—"}
            </span>

            <span class="optimized-lineup-ai">
              AI Score ${aiScoreText}
              •
              ${aiRankText}
            </span>
          </div>

          <strong>
            ${
              Number.isFinite(
                projectedPpr
              )
                ? projectedPpr.toFixed(2)
                : "—"
            }
            PPR
          </strong>
        `;

        benchGrid.appendChild(
          card
        );
      }
    );

    result.appendChild(
      benchGrid
    );
  }
}

function renderNflInactiveObservationStatus(container) {
  const existing = container.querySelector(
    ".nfl-inactive-observation-status"
  );

  if (existing) existing.remove();

  const panel = document.createElement("div");
  panel.className = "nfl-inactive-observation-status";

  Object.assign(panel.style, {
    padding: "14px 16px",
    marginBottom: "16px",
    border: "1px solid #c8a64d",
    borderRadius: "10px",
    background: "#171717",
    color: "#ffffff"
  });

  const heading = document.createElement("strong");
  heading.textContent = "NFL Game-Day Inactive Report";
  heading.style.color = "#f5d37a";

  const description = document.createElement("p");
  description.style.margin = "8px 0 0";

  // Only show reports for the current projection week. Historical inactive
  // observations must never appear as live lineup guidance.
  const targetWeek = Number(
    document.documentElement.dataset.targetWeek
  );
  // The site's target week is the canonical display week. Roster rows may
  // omit their own week, so do not infer the week from roster entries.
  const currentWeek = Number.isInteger(targetWeek) &&
    targetWeek >= 1 && targetWeek <= 22 ? targetWeek : null;
  const games = (nflInactiveObservations?.games || []).filter(
    game => currentWeek !== null &&
      Number(game.week) === currentWeek &&
      game.season === 2026
  );

  if (games.length === 0) {
    description.textContent =
      "No pregame NFL.com observations are currently available. " +
      "DATA DADDY continues using its existing player availability data.";
  } else {
    const playerCount = games.reduce(
      (total, game) => total + game.players.length,
      0
    );

    description.textContent =
      `${games.length} game reports available, covering ` +
      `${playerCount} player entries. These NFL.com observations ` +
      `are not independently verified and do not change ` +
      `lineup eligibility or projected PPR.`;
  }

  panel.append(heading, description);
  container.prepend(panel);
}



function getSaferLineupGroups(groups) {
  const risky = new Set(["QUESTIONABLE", "DOUBTFUL", "Q", "D"]);
  return Object.fromEntries(Object.entries(groups).map(([position, entries]) => [
    position,
    entries.filter(projection => {
      const player = getProjectionPlayer(projection);
      return !risky.has(String(player?.injuryStatus || "").trim().toUpperCase());
    })
  ]));
}

function optimizeLineup(mode = "best") {
  const result = document.getElementById(
    "lineupAnalyzerResult"
  );

  if (!result) return;

  const existingDialog = document.getElementById(
    "lineupAiInsightsDialog"
  );

  if (existingDialog) {
    existingDialog.remove();
  }

  const rules = getLineupRules();
  const groups = getLineupPlayersByPosition();
  const maximumLineup = findBestLegalLineup(rules, groups);
  const saferLineup = findBestLegalLineup(rules, getSaferLineupGroups(groups));
  const useSafer = mode === "safe" && Boolean(saferLineup);
  const bestLineup = useSafer ? saferLineup : maximumLineup;

  if (!bestLineup) {
    const missing = getMissingLineupNeeds(
      rules,
      groups
    );

    result.innerHTML = `
      <div class="lineup-validation-message">
        <strong>Roster is not complete yet.</strong>
        <span>
          ${
            missing.length > 0
              ? missing.join(" • ")
              : "Add more eligible players to build a legal lineup."
          }
        </span>
      </div>
    `;

    return;
  }

  renderOptimizedLineup(bestLineup, rules, useSafer ? "safe" : "best");
  if (maximumLineup) {
    const choices = document.createElement("div");
    choices.className = "lineup-strategy-choices";
    Object.assign(choices.style, { display: "flex", gap: "10px",
      flexWrap: "wrap", margin: "12px 0" });
    for (const [choice, label] of [
      ["best", "Best Projected PPR"],
      ["safe", "Avoid Questionable/Doubtful"]
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.disabled = choice === (useSafer ? "safe" : "best") || (choice === "safe" && !saferLineup);
      if (choice === "safe" && !saferLineup) button.title = "No legal lineup without questionable or doubtful players";
      button.addEventListener("click", () => optimizeLineup(choice));
      choices.appendChild(button);
    }
    const summary = document.createElement("p");
    summary.textContent = !saferLineup
      ? "No legal lineup can avoid all questionable/doubtful players with the current roster. Add eligible backups to unlock the safer strategy."
      : useSafer
        ? "Safer designation-based lineup: " + saferLineup.total.toFixed(2) +
          " projected PPR vs. maximum " + maximumLineup.total.toFixed(2) +
          ". This does not guarantee player availability."
        : "Maximum projected lineup: " + maximumLineup.total.toFixed(2) +
          " PPR. Safer designation-based option: " + saferLineup.total.toFixed(2) +
          " PPR. Injury designations can change.";
    const resultHeading = result.firstElementChild;
    if (resultHeading) resultHeading.before(choices, summary);
    else result.append(choices, summary);
  }
  const dialog = document.createElement("dialog");
  dialog.id = "lineupAiInsightsDialog";
  dialog.setAttribute(
    "aria-label",
    "DATA DADDY AI Second Opinion"
  );

  Object.assign(dialog.style, {
    width: "min(92vw, 700px)",
    maxHeight: "85vh",
    overflowY: "auto",
    padding: "24px",
    border: "1px solid #c8a64d",
    borderRadius: "16px",
    background: "#151515",
    color: "#ffffff",
    boxShadow: "0 20px 70px rgba(0,0,0,.7)"
  });

  const header = document.createElement("div");
  Object.assign(header.style, {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "16px",
    marginBottom: "20px"
  });

  const title = document.createElement("h3");
  title.textContent = "DATA DADDY — AI SECOND OPINION";
  title.style.margin = "0";
  title.style.color = "#f5d37a";

  
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.textContent = "✕ Close";

  Object.assign(closeButton.style, {
    background: "#171717",
    color: "#f5d37a",
    border: "1px solid #f5d37a",
    borderRadius: "8px",
    padding: "10px 16px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    width: "auto",
    minWidth: "90px",
    flex: "0 0 auto",
    boxShadow: "none"
  });

  closeButton.addEventListener("click", () => {
    dialog.close();
  });

  header.append(title, closeButton);
  dialog.appendChild(header);

  const existingInsights = result.querySelector(
    ".start-sit-insights"
  );

  if (existingInsights) {
    dialog.appendChild(existingInsights);

  } else {
    const heading = document.createElement("h4");
    heading.textContent = "Your Optimized Lineup — AI Analysis";
    dialog.appendChild(heading);

    const explanation = document.createElement("p");
    explanation.textContent =
      "No bench player meets the current AI disagreement " +
      "threshold. Here is an overview of your recommended " +
      "starters, based on available projections and signals.";
    dialog.appendChild(explanation);

    const slots = buildLineupSlots(bestLineup, rules);

    slots.forEach(({ slot, player: projection }) => {
      const player = getProjectionPlayer(projection);
      const card = document.createElement("div");
      card.className = "start-sit-insight-card";

      const name = document.createElement("h4");
      name.textContent =
        `${slot}: ${projection.player_name}`;

      const ppr = Number(projection.projected_ppr);
      const ai = getLineupPlayerAiData(projection);

      const details = document.createElement("p");
      details.textContent =
        `Projected PPR: ${
          Number.isFinite(ppr) ? ppr.toFixed(2) : "Unavailable"
        } | AI Score: ${
          ai.score == null ? "Unavailable" : ai.score.toFixed(1)
        }`;

      card.append(name, details);

      if (player) {
        const position = String(player.position || "").toUpperCase();
        const opponent = teamNextOpponent[player.team]?.opponent;
        const allowed = opponent
          ? defensePositionAllowed[opponent]?.[position]
          : null;

        const matchup = document.createElement("p");
        matchup.textContent =
          allowed?.fantasy_points_allowed != null
            ? `Matchup: ${opponent} | Score: ${
                calculateMatchupScore(player)
              }/100`
            : "Matchup: Unavailable";

        card.appendChild(matchup);

        const targetWeek = Number(
          document.documentElement.dataset.targetWeek
        );

        const games = getPlayerWeeklyStats(player)
          .filter(game =>
            Number(game.season) === 2026 &&
            Number(game.week) < targetWeek
          )
          .sort((a, b) => Number(b.week) - Number(a.week))
          .slice(0, 3);

        const usage = document.createElement("p");

        if (games.length) {
          const field = position === "RB"
            ? "carries"
            : position === "QB"
              ? "attempts"
              : "targets";

          const valid = games
            .map(game => Number(game[field]))
            .filter(Number.isFinite);

          usage.textContent = valid.length
            ? `Recent ${field}: ${
                (valid.reduce((a, b) => a + b, 0) /
                  valid.length).toFixed(1)
              } per game (${valid.length} games)`
            : "Recent usage: Unavailable";
        } else {
          usage.textContent = "Recent usage: Unavailable";
        }

        card.appendChild(usage);
      } else {
        const unavailable = document.createElement("p");
        unavailable.textContent =
          "Additional player signals unavailable.";
        card.appendChild(unavailable);
      }

      const recommendation = document.createElement("p");
      recommendation.style.marginTop = "12px";

      const reasons = [];
      const cautions = [];

      if (player) {
        const position = String(
          player.position || projection.position || ""
        ).toUpperCase();

        const opponent =
          teamNextOpponent[player.team]?.opponent;

        const matchupData = opponent
          ? defensePositionAllowed[opponent]?.[position]
          : null;

        if (matchupData?.fantasy_points_allowed != null) {
          const score = Number(calculateMatchupScore(player));

          if (Number.isFinite(score)) {
            if (score >= 65) {
              reasons.push("favorable matchup");
            } else if (score <= 35) {
              cautions.push("difficult matchup");
            }
          }
        }

        const status = String(
          player.injuryStatus || player.status || ""
        ).trim().toUpperCase();

        if (status === "QUESTIONABLE" || status === "DOUBTFUL") {
          cautions.push(
            `${status.toLowerCase()} injury designation`
          );
        }

        
        const targetWeek = Number(
          document.documentElement.dataset.targetWeek
        );

        const recentGames = getPlayerWeeklyStats(player)
          .filter(game =>
            Number(game.season) === 2026 &&
            Number(game.week) < targetWeek
          )
          .sort((a, b) => Number(b.week) - Number(a.week))
          .slice(0, 3);

        const average = (field) => {
          const values = recentGames
            .map(game => game[field])
            .filter(value =>
              value !== null &&
              value !== undefined &&
              value !== ""
            )
            .map(Number)
            .filter(Number.isFinite);

          return values.length >= 2
            ? values.reduce((sum, value) => sum + value, 0) /
                values.length
            : null;
        };

        const addVolumeSignal = (field, threshold, label) => {
          const value = average(field);

          if (value !== null && value >= threshold) {
            reasons.push(
              `${label} (${value.toFixed(1)}/game)`
            );
          }
        };

        if (position === "QB") {
          addVolumeSignal(
            "attempts", 30, "strong passing volume"
          );
          addVolumeSignal(
            "carries", 5, "rushing involvement"
          );
          addVolumeSignal(
            "red_zone_pass_attempts",
            4,
            "red-zone passing opportunities"
          );
        } else if (position === "RB") {
          addVolumeSignal(
            "carries", 15, "strong rushing workload"
          );
          addVolumeSignal(
            "targets", 4, "receiving involvement"
          );
          addVolumeSignal(
            "red_zone_carries",
            2,
            "red-zone rushing opportunities"
          );
        } else if (position === "WR" || position === "TE") {
          addVolumeSignal(
            "targets", 7, "strong target volume"
          );
          addVolumeSignal(
            "red_zone_targets",
            1,
            "red-zone receiving opportunities"
          );
       
        }
      }

     
      const addAnalysisSection = (heading, content, color) => {
        const section = document.createElement("div");
        section.style.cssText =
          "padding:10px 14px;margin-top:10px;" +
          "background:rgba(255,255,255,.04);" +
          "border-left:3px solid " + color + ";" +
          "border-radius:5px;";

        const label = document.createElement("strong");
        label.textContent = heading;
        label.style.color = color;
        label.style.display = "block";
        label.style.marginBottom = "5px";

        const description = document.createElement("div");
        description.textContent = content;
        description.style.lineHeight = "1.5";

        section.append(label, description);
        card.appendChild(section);
      };

      addAnalysisSection(
        "SUPPORTING SIGNALS",
        reasons.length
          ? reasons.join(" • ")
          : "No strong supporting signals identified from available data.",
        "#7dd3a8"
      );

      addAnalysisSection(
        "RISK FACTORS",
        cautions.length
          ? cautions.join(" • ")
          : "No specific risk factors flagged by the available signals.",
        "#f0b86e"
      );

      addAnalysisSection(
        "FINAL RECOMMENDATION",
        `Start ${projection.player_name} in the projected optimal ` +
        "lineup based on projected PPR. Monitor injury, role, " +
        "and matchup updates before kickoff.",
        "#f5d37a"
      );

      
      dialog.appendChild(card);
    });

    const recommendation = document.createElement("p");
    recommendation.textContent =
      "Recommendation: Keep the projected optimal lineup " +
      "unless new injury, role, or matchup information " +
      "changes the decision. AI Scores and recent usage " +
      "provide supporting context, not guaranteed outcomes.";
    dialog.appendChild(recommendation);
  }

  document.body.appendChild(dialog);

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });


  const insightsButton = document.createElement("button");
  insightsButton.type = "button";
  insightsButton.textContent = "View AI Insights";

  Object.assign(insightsButton.style, {
    display: "block",
    width: "100%",
    marginTop: "20px",
    padding: "14px 20px",
    border: "1px solid #c8a64d",
    borderRadius: "10px",
    background: "#dcae42",
    color: "#111111",
    fontWeight: "700",
    fontSize: "15px",
    cursor: "pointer"
  });

  insightsButton.addEventListener("click", () => {
    dialog.showModal();
  });

  result.appendChild(insightsButton);

  result.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}


function normalizeName(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/[.'’-]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    // Stat feeds and roster feeds often disagree on generational suffixes.
    // Remove suffixes only at the end; retain exact full-name matching.
    .replace(/ (jr|sr|ii|iii|iv|v)$/i, "");
}


const playerWeeklyStatsCache = new Map();

const teamGameStatsCache = new Map();

function getTeamGameRows(season, week, team) {
  const key = `${season}-${week}-${team}`;

  if (teamGameStatsCache.has(key)) {
    return teamGameStatsCache.get(key);
  }

  const rows = weeklyStats.filter(
    row =>
      Number(row.season) === season &&
      row.team === team &&
      Number(row.week) === week
  );

  teamGameStatsCache.set(key, rows);

  return rows;
}

function getPlayerWeeklyStats(player) {
  if (
    !player ||
    !Array.isArray(weeklyStats) ||
    weeklyStats.length === 0
  ) {
    return [];
  }

  const playerName = normalizeName(player.name);
  // Include position and team: a name-only cache can reuse another
  // player's weekly rows, distorting low-sample usage and production.
  const normalizedTeam = value =>
    ({ LA: "LAR", JAC: "JAX", WSH: "WAS" })[
      String(value || "").toUpperCase()
    ] || String(value || "").toUpperCase();
  const cacheKey = [
    playerName,
    String(player.position || "").toUpperCase(),
    normalizedTeam(player.team)
  ].join("|");

  if (playerWeeklyStatsCache.has(cacheKey)) {
    return playerWeeklyStatsCache.get(cacheKey);
  }

  const matches = weeklyStats.filter((row) => {
    const fullName = normalizeName(row.player_display_name || "");
    const shortName = normalizeName(row.player_name || "");
    const rowPosition = String(row.position || "").toUpperCase();
    const playerPosition = String(player.position || "").toUpperCase();

    // Never match a different position or a partial name. Partial-name
    // matching can silently attribute another player's targets/production.
    if (rowPosition && playerPosition && rowPosition !== playerPosition) {
      return false;
    }
    const rowTeam = normalizedTeam(row.team);
    const playerTeam = normalizedTeam(player.team);
    if (rowTeam && playerTeam && rowTeam !== playerTeam) {
      return false;
    }
    return Boolean(
      playerName &&
      (fullName === playerName || shortName === playerName)
    );
  });

  playerWeeklyStatsCache.set(cacheKey, matches);

  return matches;
}

function getProductionGameCount(player) {
  if (!player) {
    return 0;
  }

  const recentGames = getPlayerWeeklyStats(player)
    .filter(game => Number(game.season) === 2026)
    .sort((a, b) =>
      Number(b.week || 0) - Number(a.week || 0)
    )
    .slice(0, 3);

  return recentGames.length;
}

function calculateProductionScore(player) {
  const games = getPlayerWeeklyStats(player);

  if (games.length === 0) {
    return 20;
  }

  function getFantasyPoints(game) {
    const passingYards =
      Number(game.passing_yards || 0);

    const passingTDs =
      Number(game.passing_tds || 0);

    const interceptions =
      Number(game.interceptions || 0);

    const rushingYards =
      Number(game.rushing_yards || 0);

    const rushingTDs =
      Number(game.rushing_tds || 0);

    const receptions =
      Number(game.receptions || 0);

    const receivingYards =
      Number(game.receiving_yards || 0);

    const receivingTDs =
      Number(game.receiving_tds || 0);

    return (
      passingYards / 25 +
      passingTDs * 4 -
      interceptions * 2 +
      rushingYards / 10 +
      rushingTDs * 6 +
      receptions +
      receivingYards / 10 +
      receivingTDs * 6
    );
  }

  function getRecentAverage(playerGames) {
  const recentGames =
    [...playerGames]
      .filter(
        game => Number(game.season) === 2026
      )
      .sort(
        (a, b) =>
          Number(b.season || 0) -
            Number(a.season || 0) ||
          Number(b.week || 0) -
            Number(a.week || 0)
      )
      .slice(0, 3);

    if (recentGames.length === 0) {
      return 0;
    }

    // TE production responds to recent form without discarding prior games.
    // Newest-to-oldest weights: 50/30/20 for three games.
    // Other positions retain their existing equal-game average.
    if (player.position === "TE" && recentGames.length === 3) {
      return recentGames.reduce(
        (sum, game, index) =>
          sum + getFantasyPoints(game) * [0.5, 0.3, 0.2][index],
        0
      );
    }

    const total =
      recentGames.reduce(
        (sum, game) =>
          sum + getFantasyPoints(game),
        0
      );

    return total / recentGames.length;
  }

  // A player with historical rows but no 2026 appearances should not
  // receive a zero merely because the recent-season filter is empty.
  // Keep the same conservative missing-production fallback used for
  // players with no rows; a future healthy-game prior requires validation.
  const currentSeasonGames = games.filter(
    (game) => Number(game.season) === 2026
  );
  if (currentSeasonGames.length === 0) {
    return 20;
  }

  const playerAverage =
    getRecentAverage(currentSeasonGames);

  const positionPlayers = {};

  weeklyStats.forEach((game) => {
    if (game.position !== player.position) {
      return;
    }

    const name = normalizeName(
      game.player_display_name ||
      game.player_name ||
      game.name
    );

    if (!name) {
      return;
    }

    if (!positionPlayers[name]) {
      positionPlayers[name] = [];
    }

    positionPlayers[name].push(game);
  });

  const positionAverages =
    Object.values(positionPlayers)
      .map((playerGames) =>
        getRecentAverage(playerGames)
      )
      .filter((average) =>
        Number.isFinite(average) &&
        average > 0
      );

  if (positionAverages.length === 0) {
    return 50;
  }

  const leagueHigh =
    Math.max(...positionAverages);

  if (leagueHigh <= 0) {
    return 50;
  }

  const score =
    (playerAverage / leagueHigh) * 100;

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(score)
    )
  );
}

// Conservative proxy for a recurring multi-TE receiving role.
// This measures shared target production, not unobserved personnel sets.
function getMultiTeReceivingRoleBonus(player, recentGames) {
  if (player.position !== "TE" || recentGames.length < 2) return 0;
  let qualifyingGames = 0;
  for (const game of recentGames) {
    const ownTargets = Number(game.targets || 0);
    if (ownTargets < 3) continue;
    const playerName = normalizeName(player.name);
    const otherTargetedTe = getTeamGameRows(
      Number(game.season), Number(game.week), game.team
    ).some(row =>
      row.position === "TE" &&
      normalizeName(row.player_display_name || row.player_name || row.name || "") !== playerName &&
      Number(row.targets || 0) >= 2
    );
    if (otherTargetedTe) qualifyingGames += 1;
  }
  return qualifyingGames >= 2 ? 6 : 0;
}

function calculateUsageScore(player) {
  const games = getPlayerWeeklyStats(player)
    .filter(
      game => Number(game.season) === 2026
    )
    .sort(
      (a, b) =>
        Number(b.week || 0) -
        Number(a.week || 0)
    )
    .slice(0, 3);

  if (games.length === 0) {
    return 20;
  }
  // QB usage:
  // Measures fantasy-relevant rushing involvement.
  // Passing volume is already represented by Opportunity,
  // so QB Usage focuses on rushing share.
  if (player.position === "QB") {
    let totalRushingShare = 0;
    let validGames = 0;

    games.forEach((game) => {
      const season = Number(game.season);
      const week = Number(game.week);
      const team = game.team;

      if (!season || !team || !week) {
        return;
      }

      const teamGameRows =
        getTeamGameRows(
          season,
          week,
          team
        );

      const playerCarries =
        Number(
          game.carries ||
          game.rushing_attempts ||
          0
        );

      const teamCarries =
        teamGameRows.reduce(
          (total, row) =>
            total +
            Number(
              row.carries ||
              row.rushing_attempts ||
              0
            ),
          0
        );

      if (teamCarries <= 0) {
        return;
      }

      const rushingShare =
        playerCarries /
        teamCarries;

      totalRushingShare +=
        rushingShare;

      validGames += 1;
    });

    if (validGames === 0) {
      return 50;
    }

    const averageRushingShare =
      totalRushingShare /
      validGames;

    return Math.max(
      0,
      Math.min(
        100,
        Math.round(
          averageRushingShare * 400
        )
      )
    );
  }  

  // RB / WR / TE usage:
  // rushing share + target share.
  let totalShare = 0;
  let validGames = 0;
  const teTargetShares = [];

  games.forEach((game) => {
    const season = Number(game.season);
    const week = Number(game.week);
    const team = game.team;

    if (!season || !team || !week) {
      return;
    }

    const teamGameRows =
      getTeamGameRows(season, week, team);

    const playerCarries = Number(
      game.carries ||
      game.rushing_attempts ||
      0
    );

    const playerTargets =
      Number(game.targets || 0);

    const teamCarries = teamGameRows.reduce(
      (total, row) =>
        total +
        Number(
          row.carries ||
          row.rushing_attempts ||
          0
        ),
      0
    );

    const teamTargets = teamGameRows.reduce(
      (total, row) =>
        total + Number(row.targets || 0),
      0
    );

    const carryShare =
      teamCarries > 0
        ? playerCarries / teamCarries
        : 0;

    const targetShare =
      teamTargets > 0
        ? playerTargets / teamTargets
        : 0;

    totalShare +=
      carryShare + targetShare;

    if (player.position === "TE" && teamTargets > 0) {
      teTargetShares.push(targetShare);
    }

    validGames += 1;
  });

  if (validGames === 0) {
    return 50;
  }

  const averageShare =
    totalShare / validGames;

  // TE-only, bounded recent target-share trend. Games are newest first.
  // Week 6 proxy holdout: top-24 hits 16 -> 17, rank MAE 13.200 -> 13.345.
  const teTrendAdjustment = player.position === "TE" && teTargetShares.length === 3
    ? Math.max(-10, Math.min(10, Math.round(
        (teTargetShares[0] - (teTargetShares[1] + teTargetShares[2]) / 2) * 100
      )))
    : 0;

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(averageShare * 100) +
        getMultiTeReceivingRoleBonus(player, games) +
        teTrendAdjustment
    )
  );
}

// Transparent, read-only evidence for the three core AI signals.
// These figures use the same recent 2026 weekly rows as the score functions.
// Consistent white-label / gold-value evidence rows across signal panels.
function signalEvidenceRows(rows) {
  const escape = value => String(value ?? "Unavailable").replace(/[&<>"']/g, char =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  return '<div class="confidence-breakdown core-signal-breakdown">' +
    rows.map(([label, value]) =>
      '<div><strong>' + escape(label) +
      '</strong><span class="core-signal-value" style="color:#fbbf24 !important;font-weight:800;">' +
      escape(value) + '</span></div>'
    ).join("") + '</div>';
}
function getAdditionalSignalEvidence(player, label, details, confidence, trench) {
  const rows = [];
  const add = (name, value) => rows.push([name, value ?? "Unavailable"]);
  const display = value => value === null || value === undefined || value === "" ? "Unavailable" : value;
  if (label === "Matchup") {
    const opponent = teamNextOpponent[player.team]?.opponent;
    const record = opponent && defensePositionAllowed[opponent]?.[player.position];
    const raw = record?.fantasy_points_allowed;
    const allowed = raw === null || raw === undefined || raw === "" ? NaN : Number(raw);
    const ranked = Object.entries(defensePositionAllowed)
      .map(([team, positions]) => ({
        team,
        allowed: positions?.[player.position]?.fantasy_points_allowed
      }))
      .filter(entry => entry.allowed !== null && entry.allowed !== undefined &&
        entry.allowed !== "" && Number.isFinite(Number(entry.allowed)))
      .map(entry => ({team: entry.team, allowed: Number(entry.allowed)}))
      .sort((a,b) => b.allowed - a.allowed);
    const rank = ranked.findIndex(entry => entry.team === opponent);
    const countRaw = record?.sample_size_2026 ?? record?.games_evaluated ??
      record?.games_played ?? record?.sample_size ?? null;
    const count = countRaw === null || countRaw === "" ? NaN : Number(countRaw);
    add("Opponent", opponent || "Unavailable");
    add("Position", player.position);
    add("Opponent PPR allowed to position", Number.isFinite(allowed) ?
      allowed.toFixed(1) + " per game (all " + player.position + "s)" : "Unavailable");
    add("Matchup favorability rank", rank >= 0 ?
      "#" + (rank + 1) + " of " + ranked.length + " defenses" : "Unavailable");
    add("Ranking direction", "#1 allows the most PPR to this position");
    add("Games in defensive sample", Number.isFinite(count) && count > 0 ?
      String(count) : "Not supplied by feed");
    add("Data scope", "Team positional total, not individual player");
  } else if (label === "Play Caller Matchup" || label === "Player vs Defensive Play Caller") {
    const isPlayerHistory = label === "Player vs Defensive Play Caller";
    if (!isPlayerHistory && details?.offensivePlayCaller && details.offensivePlayCaller !== "Unknown")
      add("Offensive play caller", details.offensivePlayCaller);
    if (details?.defensivePlayCaller && details.defensivePlayCaller !== "Unknown")
      add("Defensive play caller", details.defensivePlayCaller);
    if (details?.opponent && details.opponent !== "Unknown")
      add("Opponent", details.opponent);
    const meetings = Number(details?.sampleSize);
    if (Number.isFinite(meetings) && meetings > 0) {
      add(isPlayerHistory ? "Player matchup sample" : "Play caller matchup sample", meetings + " games");
      if (details?.averagePpr != null && details.averagePpr !== "" &&
          Number.isFinite(Number(details.averagePpr)))
        add(isPlayerHistory ? "Player historical PPR / game" : "Combined positional PPR / game",
          Number(details.averagePpr).toFixed(1));
      if (meetings < 3) add("Historical sample", "Limited (" + meetings + " of 3 games)");
      const games = Array.isArray(details?.games) ? details.games.slice(0,3) : [];
      for (const game of games) {
        const season = Number(game.season);
        const week = Number(game.week);
        const points = game.ppr ?? game.ppr_points ?? game.fantasy_points_ppr;
        if (!Number.isInteger(season) || !Number.isInteger(week) ||
            points == null || !Number.isFinite(Number(points))) continue;
        const opponent = String(game.opponent || game.opponent_team || "").trim();
        add("Week " + week + " (" + season + ")" + (opponent ? " vs " + opponent : ""),
          Number(points).toFixed(1) + " PPR");
      }
    } else {
      add("Historical sample", "No direct meetings; neutral score");
    }
  } else if (label === "Red-Zone Usage") {
    const record = getWeightedRedZoneRecord(player);
    if (record?.zones) {
      add("Games evaluated", display(record.games_evaluated));
      for (const [name, key] of [["20–11 yards", "20_11"], ["10–6 yards", "10_6"], ["Inside the 5", "5_1"]]) {
        const zone = record.zones[key];
        if (zone) add(name, Number(zone.carries || 0) + Number(zone.targets || 0) + " opportunities (" + Number(zone.carries || 0) + " carries, " + Number(zone.targets || 0) + " targets)");
      }
      add("Weighted opportunities / game", Number(record.weighted_opportunities_per_game).toFixed(2));
    } else {
      const games = getPlayerWeeklyStats(player).filter(g => Number(g.season) === 2026)
        .sort((a,b) => Number(b.week || 0) - Number(a.week || 0)).slice(0,3);
      add("Games evaluated", games.length);
      add("Red-zone carries", games.length ? games.reduce((n,g) => n + Number(g.red_zone_carries || 0),0) : "Unavailable");
      if (player.position === "QB") {
        add("Red-zone pass attempts", games.length ? games.reduce((n,g) => n + Number(g.red_zone_pass_attempts || 0),0) : "Unavailable");
      } else {
        add("Red-zone targets", games.length ? games.reduce((n,g) => n + Number(g.red_zone_targets || 0),0) : "Unavailable");
      }
    }
  } else if (label === "Scoring Environment") {
    const env = getScoringEnvironment(player);
    add("Opponent", env?.opponent || "Unavailable");
    add("Week", env?.week || "Unavailable");
    add("Implied team points", display(env?.impliedTeamTotal));
    add("Game total", display(env?.gameTotal));
    add("Spread", display(env?.spread));
    add("Source", env?.source || "Unavailable");
  } else if (label === "Model Confidence") {
    add("Production consistency", confidence?.productionConsistency != null ? confidence.productionConsistency + "/100" : "Unavailable");
    add("Opportunity stability", confidence?.opportunityStability != null ? confidence.opportunityStability + "/100" : "Unavailable");
    add("Usage stability", confidence?.usageStability != null ? confidence.usageStability + "/100" : "Unavailable");
    add("Availability", confidence?.availability != null ? confidence.availability + "/100" : "Unavailable");
  } else if (label === "Risk Adjustment") {
    add("Roster status", player.status || "Unavailable");
    add("Injury designation", player.injuryStatus || "None reported");
    add("Practice participation", player.practiceParticipation || "Not reported");
    add("Depth chart", player.depthChartOrder != null ? "#" + player.depthChartOrder : "Unavailable");
    add("Risk method", "Rule-based; not a probability");
  } else if (label === "Trench Matchup") {
    if (trench) {
      add("Opponent", trench.opponent);
      add("Overall trench matchup", trench.score.toFixed(1) + "/100");
      add("Pass matchup", trench.passScore.toFixed(1) + "/100");
      add("Run matchup", trench.runScore.toFixed(1) + "/100");
      const rate = (label, value) => {
        if (value !== null && value !== undefined && Number.isFinite(Number(value))) {
          add(label, Number(value).toFixed(2) + "%");
        }
      };
      rate("Offense sacks allowed / pass play", trench.offenseSackRate);
      rate("Offense QB hits allowed / pass play", trench.offenseQbHitRate);
      rate("Offense rushing success rate", trench.offenseRushSuccessRate);
      rate("Defense sacks / pass play", trench.defenseSackRate);
      rate("Defense QB hits / pass play", trench.defenseQbHitRate);
      rate("Defense run-stop rate", trench.defenseRunStopRate);
    }
  }
  return rows.length ? signalEvidenceRows(rows) : "";
}
function getCoreSignalEvidence(player, signal) {
  const games = getPlayerWeeklyStats(player)
    .filter(game => Number(game.season) === 2026)
    .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
    .slice(0, 3);
  if (!games.length) return "2026 · No recorded games · underlying data unavailable";
  const num = (row, ...keys) => {
    for (const key of keys) {
      if (row[key] !== undefined && row[key] !== null && row[key] !== "") {
        const value = Number(row[key]);
        if (Number.isFinite(value)) return value;
      }
    }
    return 0;
  };
  const total = (fn) => games.reduce((sum, game) => sum + fn(game), 0);
  const avg = value => (value / games.length).toFixed(1);
  const carries = game => num(game, "carries", "rushing_attempts");
  const targets = game => num(game, "targets");
  const attempts = game => num(game, "attempts", "passing_attempts");
  const lines = [];
  const add = (label, value) => lines.push([label, String(value)]);
  if (signal === "Opportunity") {
    add("Games evaluated", games.length + " (most recent)");
    if (player.position === "QB") {
      add("Pass attempts / game", avg(total(attempts)));
      add("Carries / game", avg(total(carries)));
      add("Combined opportunities / game", avg(total(g => attempts(g) + carries(g))));
    } else {
      add("Targets / game", avg(total(targets)));
      add("Carries / game", avg(total(carries)));
      add("Combined opportunities / game", avg(total(g => targets(g) + carries(g))));
    }
  } else if (signal === "Recent Production") {
    const points = game =>
      num(game, "passing_yards") / 25 +
      num(game, "passing_tds") * 4 -
      num(game, "interceptions") * 2 +
      num(game, "rushing_yards") / 10 +
      num(game, "rushing_tds") * 6 +
      num(game, "receptions") +
      num(game, "receiving_yards") / 10 +
      num(game, "receiving_tds") * 6;
    const ppr = games.map(points);
    add("Games evaluated", games.length + " (newest first)");
    add("PPR by week", games.map((g, i) => "W" + g.week + " " + ppr[i].toFixed(1)).join(" · "));
    add("Average PPR / game", avg(ppr.reduce((a, b) => a + b, 0)));
    if (player.position === "TE" && games.length === 3) {
      add("TE weighted recent PPR", (ppr[0] * .5 + ppr[1] * .3 + ppr[2] * .2).toFixed(1) + " (50/30/20)");
    }
  } else if (signal === "Usage") {
    const shares = [];
    for (const game of games) {
      const season = Number(game.season), week = Number(game.week);
      if (!season || !week || !game.team) continue;
      const teamRows = getTeamGameRows(season, week, game.team);
      if (!Array.isArray(teamRows) || !teamRows.length) continue;
      const teamCarries = teamRows.reduce((sum, row) => sum + carries(row), 0);
      const teamTargets = teamRows.reduce((sum, row) => sum + targets(row), 0);
      shares.push({
        rush: teamCarries > 0 ? carries(game) / teamCarries * 100 : null,
        target: teamTargets > 0 ? targets(game) / teamTargets * 100 : null
      });
    }
    add("Player games", games.length);
    add("Team-share games", shares.length);
    const averageShare = key => {
      const values = shares.map(x => x[key]).filter(x => x !== null);
      return values.length
        ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) + "%"
        : "Unavailable";
    };
    add("Team rushing-attempt share", averageShare("rush"));
    if (player.position !== "QB") add("Team target share", averageShare("target"));
    add("Method", player.position === "QB" ? "QB rushing share" : "Rushing and target shares");
  }
  if (games.length < 3) add("Sample warning", "Fewer than 3 games");
  return '<div class="confidence-breakdown core-signal-breakdown">' +
    lines.map(([label, value]) =>
      '<div><strong>' + label + '</strong><span class="core-signal-value" style="color:#fbbf24 !important;font-weight:800;">' + value + '</span></div>'
    ).join("") + '</div>';
}

function getOpportunityGameCount(player) {
  if (!player) {
    return 0;
  }

  const playerName = normalizeName(player.name);

  const matchingGames = getPlayerWeeklyStats(player)
    .filter(game =>
      Number(game.season) === 2026 &&
      game.position === player.position &&
      normalizeName(
        game.player_display_name ||
        game.player_name ||
        game.name
      ) === playerName
    )
    .sort((a, b) =>
      Number(b.week || 0) - Number(a.week || 0)
    );

    return Math.min(3, matchingGames.length);
}

  
function calculateOpportunityScore(player) {
  const games = getPlayerWeeklyStats(player);

  if (games.length === 0) {
    return 20;
  }

  const position = player.position;
  const playerTotals = {};

  weeklyStats
    .filter(
      game =>
        game.position === position &&
        Number(game.season) === 2026
    )
    .sort(
      (a, b) =>
        Number(b.week || 0) -
        Number(a.week || 0)
    )
    .forEach((game) => {

    const name = normalizeName(
      game.player_display_name ||
      game.player_name ||
      game.name
    );

    if (!name) {
      return;
    }

    if (!playerTotals[name]) {
      playerTotals[name] = {
        opportunities: 0,
        games: 0
      };
    }

    if (playerTotals[name].games >= 3) {
      return;
    }

    const carries = Number(
      game.carries ||
      game.rushing_attempts ||
      0
    );

    const targets = Number(game.targets || 0);

    const passAttempts = Number(
      game.attempts ||
      game.passing_attempts ||
      0
    );

    let opportunities = 0;

    if (position === "QB") {
      opportunities =
        passAttempts + carries;
    }

    if (position === "RB") {
      opportunities =
        carries + targets;
    }

    if (
      position === "WR" ||
      position === "TE"
    ) {
      opportunities =
        targets + carries;
    }

    playerTotals[name].opportunities +=
      opportunities;

    playerTotals[name].games += 1;
  });

  const playerAverages = Object.values(playerTotals)
    .filter((data) => data.games > 0)
    .map(
      (data) =>
        data.opportunities / data.games
    );

  if (playerAverages.length === 0) {
    return 50;
  }

  const leagueHigh =
    Math.max(...playerAverages);

  const playerName = normalizeName(player.name);
  const playerData = playerTotals[playerName];

  if (!playerData || playerData.games === 0) {
    // No recorded 2026 opportunity is not average opportunity.
    // TE reserves with no target/carry sample should not be rewarded
    // with a neutral 50 that can inflate their weekly AI rank.
    // Retain the historical fallback for other positions until audited.
    return position === "TE" ? 20 : 50;
  }

  const playerAverage =
    playerData.opportunities /
    playerData.games;

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(
        (playerAverage / leagueHigh) * 100
      )
    )
  );
}
function calculateRedZoneScore(player) {

  if (["RB", "WR", "TE"].includes(player.position)) {
    const record = getWeightedRedZoneRecord(player);

    if (!record || record.red_zone_score == null) {
      return 50; // Neutral fallback when data is unavailable
    }

    const score = Number(record.red_zone_score);

    return Number.isFinite(score)
      ? Math.max(0, Math.min(100, score))
      : 50;
  }


  
  const games = getPlayerWeeklyStats(player)
    .filter(
      game => Number(game.season) === 2026
    )
    .sort(
      (a, b) =>
        Number(b.week || 0) -
        Number(a.week || 0)
    )
    .slice(0, 3);

  if (games.length === 0) {
    return 50;
  }

  if (player.position === "QB") {
    const qbTotals = {};

    weeklyStats
      .filter(
        game =>
          game.position === "QB" &&
          Number(game.season) === 2026
      )
      .sort(
        (a, b) =>
          Number(b.week || 0) -
          Number(a.week || 0)
      )
    .forEach((game) => {
    const name = normalizeName(
        game.player_display_name ||
        game.player_name ||
        game.name
      );

      if (!name) {
        return;
      }

      if (!qbTotals[name]) {
        qbTotals[name] = {
          redZoneOpportunities: 0,
          games: 0
        };
      }

      if (qbTotals[name].games >= 3) {
        return;
      }

      const rzPassAttempts = Number(
        game.red_zone_pass_attempts || 0
      );

      const rzCarries = Number(
        game.red_zone_carries || 0
      );

      qbTotals[name].redZoneOpportunities +=
        rzPassAttempts + rzCarries;

      qbTotals[name].games += 1;
    });

    const qbAverages = Object.values(qbTotals)
      .filter((qb) => qb.games > 0)
      .map(
        (qb) =>
          qb.redZoneOpportunities / qb.games
      );

    if (qbAverages.length === 0) {
      return 50;
    }

    const leagueHigh = Math.max(...qbAverages);

    if (leagueHigh <= 0) {
      return 50;
    }

    const playerName = normalizeName(player.name);
    const playerData = qbTotals[playerName];

    if (!playerData || playerData.games === 0) {
      return 50;
    }

    const playerAverage =
      playerData.redZoneOpportunities /
      playerData.games;

    return Math.max(
      0,
      Math.min(
        100,
        Math.round(
          (playerAverage / leagueHigh) * 100
        )
      )
    );
  }


  const validGames = games.filter(
    game =>
      Number.isFinite(Number(game.season)) &&
      Number.isFinite(Number(game.week))
  );

  if (validGames.length === 0) {
    return 50;
  }

  const totalOpportunities = validGames.reduce(
    (total, game) => {
      if (player.position === "RB") {
        return total +
          Number(game.red_zone_carries || 0);
      }

      return total +
        Number(game.red_zone_targets || 0);
    },
    0
  );

  const opportunitiesPerGame =
    totalOpportunities / validGames.length;

  const benchmark =
    player.position === "RB" ? 4 : 2;

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(
        (opportunitiesPerGame / benchmark) * 100
      )
    )
  );
}
function calculateMatchupScore(player) {
  if (
    !player ||
    !player.team ||
    !player.position
  ) {
    return 50;
  }

  const teamCode =
    player.team;

  const nextGame =
    teamNextOpponent[teamCode];
  if (
    !nextGame ||
    !nextGame.opponent
  ) {
    return 50;
  }

  const opponent =
    nextGame.opponent;

  const opponentDefense =
    defensePositionAllowed[opponent];

  if (
    !opponentDefense ||
    opponentDefense[player.position] === undefined
  ) {
    return 50;
  }

const opponentPointsAllowed =
  Number(
    opponentDefense[player.position]
      ?.fantasy_points_allowed
  );

const positionValues = Object.values(
  defensePositionAllowed
)
  .map((defense) =>
    Number(
      defense[player.position]
        ?.fantasy_points_allowed
    )
  )
  .filter((value) =>
    Number.isFinite(value)
  );

  if (positionValues.length < 2) {
    return 50;
  }

  const leagueHigh =
    Math.max(...positionValues);

  const leagueLow =
    Math.min(...positionValues);

  if (leagueHigh === leagueLow) {
    return 50;
  }
  
  const normalized =
    (
      (opponentPointsAllowed - leagueLow) /
      (leagueHigh - leagueLow)
    );

  const score =
    20 + normalized * 60;

  return Math.max(
    20,
    Math.min(
      80,
      Math.round(score)
    )
  );
}
function calculatePlayCallerMatchupScore(player) {
  if (
    !player ||
    !player.team ||
    !player.position
  ) {
    return 50;
  }

const teamCode = player.team;

const teamSignal =
  currentPlayCallerSignals[teamCode];

  if (
    !teamSignal ||
    !teamSignal.positions
  ) {
    return 50;
  }

  const positionSignal =
    teamSignal.positions[player.position];

  if (!positionSignal) {
    return 50;
  }

const rawScore = Number(
  positionSignal.score
);

if (!Number.isFinite(rawScore)) {
  return 50;
}

const sampleSize =
  Number(positionSignal.sample_size || 0);

let sampleConfidence = 0;

if (sampleSize >= 3) {
  sampleConfidence = 1;
} else if (sampleSize === 2) {
  sampleConfidence = 0.6;
} else if (sampleSize === 1) {
  sampleConfidence = 0.4;
}

const adjustedScore =
  50 +
  (rawScore - 50) *
  sampleConfidence;

return Math.max(
  0,
  Math.min(
    100,
    Math.round(adjustedScore)
  )
);
}
function calculatePlayerVsDefensiveCallerScore(player) {
  if (!player || !player.name) {
    return 50;
  }

  const playerName =
    normalizeName(player.name);

  const matchingEntry =
    Object.values(
      currentPlayerVsDefensiveCaller
    ).find((signal) => {
      const signalName =
        normalizeName(
          signal.player_name ||
          signal.name ||
          ""
        );

      return signalName === playerName;
    });

  if (!matchingEntry) {
    return 50;
  }

  const rawScore =
  Number(matchingEntry.score);

if (!Number.isFinite(rawScore)) {
  return 50;
}

const sampleSize =
  Number(matchingEntry.sample_size || 0);

let sampleConfidence = 0;

if (sampleSize >= 3) {
  sampleConfidence = 1;
} else if (sampleSize === 2) {
  sampleConfidence = 0.6;
} else if (sampleSize === 1) {
  sampleConfidence = 0.4;
}

const adjustedScore =
  50 +
  (rawScore - 50) *
  sampleConfidence;

return Math.max(
  0,
  Math.min(
    100,
    Math.round(adjustedScore)
  )
);
}
function getPlayCallerMatchupDetails(player) {
  if (
    !player ||
    !player.team ||
    !player.position
  ) {
    return null;
  }

const teamCode = player.team;

const teamSignal =
  currentPlayCallerSignals[teamCode] ||
  currentPlayCallerSignals[player.team];

  if (
    !teamSignal ||
    !teamSignal.positions
  ) {
    return null;
  }

  const positionSignal =
    teamSignal.positions[player.position];

  if (!positionSignal) {
    return null;
  }

  return {
offensivePlayCaller:
  teamSignal.offensive_play_caller ||
  getPlayerWeeklyStats(player)
    .find(game => game.offensive_play_caller)
    ?.offensive_play_caller ||
  "Unknown",

    defensivePlayCaller:
      teamSignal.opponent_defensive_play_caller ||
      "Unknown",

opponent:
  (
    teamNextOpponent[player.team] ||
    teamNextOpponent[
      player.team === "LAR" ? "LA" : "LAR"
    ]
  )?.opponent || "Unknown",

    averagePpr:
      positionSignal.average_ppr,

    sampleSize:
      Number(positionSignal.sample_size || 0),
    games: positionSignal.games || positionSignal.historical_games || []
  };
}


function getPlayerVsDefensiveCallerDetails(player) {
  if (!player || !player.name) {
    return null;
  }

  const playerName =
    normalizeName(player.name);

  const matchingEntry =
    Object.values(
      currentPlayerVsDefensiveCaller
    ).find((signal) => {
      const signalName =
        normalizeName(
          signal.player_name ||
          signal.name ||
          ""
        );

      return signalName === playerName;
    });

  if (!matchingEntry) {
    return null;
  }

  return {
    defensivePlayCaller:
      matchingEntry.defensive_play_caller ||
      "Unknown",

opponent:
  (
    teamNextOpponent[player.team] ||
    teamNextOpponent[
      player.team === "LAR" ? "LA" : "LAR"
    ]
  )?.opponent || "Unknown",

    averagePpr:
      matchingEntry.average_ppr,

    sampleSize:
      Number(matchingEntry.sample_size || 0),
    games: matchingEntry.games || matchingEntry.historical_games || []
  };
}

function calculateModelConfidence(player) {
  const games = getPlayerWeeklyStats(player);

  if (games.length === 0) {
    return 50;
  }

  const recentGames = [...games]
    .filter(
      game => Number(game.season) === 2026
    )
    .sort(
      (a, b) =>
        Number(b.week || 0) -
        Number(a.week || 0)
    )
    .slice(0, 3);
  if (recentGames.length < 2) {
    return 50;
  }

  function stabilityScore(values) {
    const validValues = values.filter(
      (value) => Number.isFinite(value)
    );

    if (validValues.length < 2) {
      return 50;
    }

    const average =
      validValues.reduce(
        (total, value) => total + value,
        0
      ) / validValues.length;

    if (average <= 0) {
      return 50;
    }

    const variance =
      validValues.reduce(
        (total, value) =>
          total +
          Math.pow(value - average, 2),
        0
      ) / validValues.length;

    const standardDeviation =
      Math.sqrt(variance);

    const coefficientOfVariation =
      standardDeviation / average;

    const score =
      100 - coefficientOfVariation * 100;

    return Math.max(
      20,
      Math.min(
        100,
        Math.round(score)
      )
    );
  }

  const fantasyPoints = recentGames.map(
    (game) => {
      const passingYards =
        Number(game.passing_yards || 0);

      const passingTDs =
        Number(game.passing_tds || 0);

      const interceptions =
        Number(game.interceptions || 0);

      const rushingYards =
        Number(game.rushing_yards || 0);

      const rushingTDs =
        Number(game.rushing_tds || 0);

      const receptions =
        Number(game.receptions || 0);

      const receivingYards =
        Number(game.receiving_yards || 0);

      const receivingTDs =
        Number(game.receiving_tds || 0);

      return (
        passingYards / 25 +
        passingTDs * 4 -
        interceptions * 2 +
        rushingYards / 10 +
        rushingTDs * 6 +
        receptions +
        receivingYards / 10 +
        receivingTDs * 6
      );
    }
  );

  const opportunityValues =
    recentGames.map((game) => {
      const carries =
        Number(game.carries || 0);

      const targets =
        Number(game.targets || 0);

      const passAttempts =
        Number(game.attempts || 0);

      if (player.position === "QB") {
        return passAttempts + carries;
      }

      if (player.position === "RB") {
        return carries + targets;
      }

      return targets + carries;
    });

  const usageValues =
  recentGames.map((game) => {
    const season = Number(game.season);
    const week = Number(game.week);
    const team = game.team;

    if (!season || !team || !week) {
      return 0;
    }

    const teamGameRows =
      weeklyStats.filter(
        (row) =>
          Number(row.season) === season &&
          row.team === team &&
          Number(row.week) === week
      );
      if (player.position === "QB") {
        const playerPassAttempts =
          Number(
            game.attempts ||
            game.passing_attempts ||
            0
          );

        const playerCarries =
          Number(
            game.carries ||
            game.rushing_attempts ||
            0
          );

        const teamPassAttempts =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(
                row.attempts ||
                row.passing_attempts ||
                0
              ),
            0
          );

        const teamCarries =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(
                row.carries ||
                row.rushing_attempts ||
                0
              ),
            0
          );

        const passingShare =
          teamPassAttempts > 0
            ? playerPassAttempts /
              teamPassAttempts
            : 0;

        const rushingShare =
          teamCarries > 0
            ? playerCarries /
              teamCarries
            : 0;

        return (
          passingShare +
          rushingShare
        );
      }
      if (
        player.position === "WR" ||
        player.position === "TE"
      ) {
        const teamTargets =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(row.targets || 0),
            0
          );

        if (teamTargets <= 0) {
          return 0;
        }

        return (
          Number(game.targets || 0) /
          teamTargets
        );
      }

      const teamCarries =
        teamGameRows.reduce(
          (total, row) =>
            total +
            Number(row.carries || 0),
          0
        );

      if (teamCarries <= 0) {
        return 0;
      }

      return (
        Number(game.carries || 0) /
        teamCarries
      );
    });

  const productionConsistency =
    stabilityScore(fantasyPoints);

  const opportunityStability =
    stabilityScore(opportunityValues);

  const usageStability =
    stabilityScore(usageValues);

  const availability =
    100 - calculatePlayerRisk(player);

  const confidence =
    productionConsistency * 0.35 +
    opportunityStability * 0.30 +
    usageStability * 0.20 +
    availability * 0.15;

  return Math.max(
    20,
    Math.min(
      100,
      Math.round(confidence)
    )
  );
}
function getModelConfidenceBreakdown(player) {
  const games = getPlayerWeeklyStats(player);

  if (games.length < 2) {
    return null;
  }

  const recentGames = [...games]
    .filter(
      game => Number(game.season) === 2026
    )
    .sort(
      (a, b) =>
        Number(b.week || 0) -
        Number(a.week || 0)
    )
    .slice(0, 3);
  function stabilityScore(values) {
    const validValues = values.filter(
      (value) => Number.isFinite(value)
    );

    if (validValues.length < 2) {
      return 50;
    }

    const average =
      validValues.reduce(
        (total, value) => total + value,
        0
      ) / validValues.length;

    if (average <= 0) {
      return 50;
    }

    const variance =
      validValues.reduce(
        (total, value) =>
          total +
          Math.pow(value - average, 2),
        0
      ) / validValues.length;

    const standardDeviation =
      Math.sqrt(variance);

    const coefficientOfVariation =
      standardDeviation / average;

    return Math.max(
      20,
      Math.min(
        100,
        Math.round(
          100 -
          coefficientOfVariation * 100
        )
      )
    );
  }

  const fantasyPoints =
    recentGames.map((game) => (
      Number(game.passing_yards || 0) / 25 +
      Number(game.passing_tds || 0) * 4 -
      Number(game.interceptions || 0) * 2 +
      Number(game.rushing_yards || 0) / 10 +
      Number(game.rushing_tds || 0) * 6 +
      Number(game.receptions || 0) +
      Number(game.receiving_yards || 0) / 10 +
      Number(game.receiving_tds || 0) * 6
    ));

  const opportunityValues =
    recentGames.map((game) => {
      const carries =
        Number(game.carries || 0);

      const targets =
        Number(game.targets || 0);

      const passAttempts =
        Number(game.attempts || 0);

      if (player.position === "QB") {
        return passAttempts + carries;
      }

      if (player.position === "RB") {
        return carries + targets;
      }

      return targets + carries;
    });

  const usageValues =
  recentGames.map((game) => {
    const season = Number(game.season);
    const week = Number(game.week);
    const team = game.team;

    const teamGameRows =
      weeklyStats.filter(
        (row) =>
          Number(row.season) === season &&
          row.team === team &&
          Number(row.week) === week
      );
    
      if (player.position === "QB") {
        const playerPassAttempts =
          Number(
            game.attempts ||
            game.passing_attempts ||
            0
          );

        const playerCarries =
          Number(
            game.carries ||
            game.rushing_attempts ||
            0
          );

        const teamPassAttempts =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(
                row.attempts ||
                row.passing_attempts ||
                0
              ),
            0
          );

        const teamCarries =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(
                row.carries ||
                row.rushing_attempts ||
                0
              ),
            0
          );

        const passingShare =
          teamPassAttempts > 0
            ? playerPassAttempts /
              teamPassAttempts
            : 0;

        const rushingShare =
          teamCarries > 0
            ? playerCarries /
              teamCarries
            : 0;

        return (
          passingShare +
          rushingShare
        );
      }
      if (
        player.position === "WR" ||
        player.position === "TE"
      ) {
        const teamTargets =
          teamGameRows.reduce(
            (total, row) =>
              total +
              Number(row.targets || 0),
            0
          );

        return teamTargets > 0
          ? Number(game.targets || 0) /
            teamTargets
          : 0;
      }

      const teamCarries =
        teamGameRows.reduce(
          (total, row) =>
            total +
            Number(row.carries || 0),
          0
        );

      return teamCarries > 0
        ? Number(game.carries || 0) /
          teamCarries
        : 0;
    });

  return {
    productionConsistency:
      stabilityScore(fantasyPoints),

    opportunityStability:
      stabilityScore(opportunityValues),

    usageStability:
      stabilityScore(usageValues),

    availability:
      100 - calculatePlayerRisk(player)
  };
}
function setupPlayerSearch(input, resultsBox, selectElement) {
  if (!input || !resultsBox || !selectElement) return;

  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();
    resultsBox.innerHTML = "";

    if (!query) {
      resultsBox.classList.remove("active");
      return;
    }

    const matches = players
      .filter((player) =>
        `${player.name} ${player.position} ${player.team}`
          .toLowerCase()
          .includes(query)
      )
      .slice(0, 8);

    if (matches.length === 0) {
      resultsBox.innerHTML =
        '<div class="player-search-empty">No players found</div>';
      resultsBox.classList.add("active");
      return;
    }

    matches.forEach((player) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "player-search-option";
      option.innerHTML = `
        <strong>${player.name}</strong>
        <span>${player.position} • ${player.team}</span>
      `;

      option.addEventListener("click", () => {
        selectElement.value = player.id;
        input.value = `${player.name} — ${player.position} — ${player.team}`;
        resultsBox.innerHTML = "";
        resultsBox.classList.remove("active");
      });

      resultsBox.appendChild(option);
    });

    resultsBox.classList.add("active");
  });

  input.addEventListener("focus", () => {
    if (input.value.length > 0) {
      input.dispatchEvent(new Event("input"));
    }
  });
}

async function loadPlayers() {
  try {
    const positions = ["QB", "RB", "WR", "TE"];

    const requests = positions.map((position) =>
      fetch(`https://api.sleeper.app/v1/players/nfl?position=${position}&active=true`)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Could not load ${position} players`);
          }
          return response.json();
        })
    );

    const responses = await Promise.all(requests);
    sleeperInjuryFetchedAt = Date.now();
    const sleeperPlayers = responses.flatMap((playerMap) =>
      Object.values(playerMap)
    );

    const uniquePlayers = new Map();

    sleeperPlayers.forEach((player) => {
      if (
        player.player_id &&
        player.first_name &&
        player.last_name &&
        player.team &&
        ["QB", "RB", "WR", "TE"].includes(player.position)
      ) {
        uniquePlayers.set(player.player_id, {
          id: player.player_id,
          nflId: player.gsis_id || null,
          name: `${player.first_name} ${player.last_name}`,
          position: player.position,
          team: player.team,
          status: player.status || "Unknown",
          injuryStatus: player.injury_status || null,
          injuryStartDate: player.injury_start_date || null,
          practiceParticipation: player.practice_participation || null,
          depthChartPosition: player.depth_chart_position ?? null,
          depthChartOrder: player.depth_chart_order ?? null,
          age: player.age ?? null,
          yearsExp: player.years_exp ?? null,
          number: player.number ?? null
        });
      }
    });

const positionOrder = {
  QB: 1,
  RB: 2,
  WR: 3,
  TE: 4
};

const normalizeLookupName = name =>
  String(name || "")
    .toLowerCase()
    .replace(/[.'’\-]/g, "")
    .replace(/\s+(jr|sr|ii|iii|iv|v)$/i, "")
    .replace(/\s+/g, " ")
    .trim();

const normalizeLookupTeam = team =>
  ({
    LA: "LAR",
    JAC: "JAX",
    WSH: "WAS"
  })[team] || team;

/*
 * Start with Sleeper players because Sleeper
 * supplies injury, practice and depth-chart
 * metadata used by the UI.
 */
players = Array.from(
  uniquePlayers.values()
);

/*
 * Match Sleeper records to the authoritative
 * NFL/GSIS IDs produced by our backend.
 */

players.forEach(player => {
  const entries = Object.entries(nflPlayerLookup);

  const idMatches = entries.filter(
    ([id]) =>
      player.nflId &&
      String(player.nflId) === String(id)
  );

  const nameTeamMatches = entries.filter(
    ([id, nfl]) =>
      normalizeLookupName(player.name) ===
        normalizeLookupName(nfl.name) &&
      normalizeLookupTeam(player.team) ===
        normalizeLookupTeam(nfl.team)
  );

  const matches = idMatches.length
    ? idMatches
    : nameTeamMatches;

  if (matches.length === 1) {
    player.nflId = matches[0][0];
  } else if (matches.length > 1) {
    console.warn(
      "Ambiguous NFL player identity:",
      player.name,
      player.team,
      matches.map(([id]) => id)
    );
  }
});


/*
 * The backend weekly model is authoritative
 * for the weekly player universe.
 *
 * If Update NFL Stats produced a Fantasy AI
 * score for a QB/RB/WR/TE, make sure that
 * player exists in the frontend even when
 * Sleeper does not return him.
 */
Object.entries(nflPlayerLookup)
  .forEach(([nflId, nfl]) => {
    const position =
      String(
        nfl.position || ""
      ).toUpperCase();

    if (
      !["QB", "RB", "WR", "TE"]
        .includes(position)
    ) {
      return;
    }

    const hasBackendScore =
      fantasyAiScores[nflId] !== undefined &&
      fantasyAiScores[nflId] !== null;

    if (!hasBackendScore) {
      return;
    }

    const alreadyExists =
      players.some(player =>
        String(player.nflId || "") ===
          String(nflId)
      );

    if (alreadyExists) {
      return;
    }

    players.push({
      id: nflId,
      nflId: nflId,
      name:
        nfl.name ||
        `NFL Player ${nflId}`,
      position: position,
      team:
        normalizeLookupTeam(
          nfl.team || ""
        ),
      status: "UNKNOWN",
      injuryStatus: null,
      injuryStartDate: null,
      practiceParticipation: null,
      depthChartPosition: null,
      depthChartOrder: null,
      age: null,
      yearsExp: null,
      number: null,
      backendAdded: true
    });
  });

// The weekly projection universe may contain a recent rookie before
// Sleeper or the current backend lookup recognizes him. Add only those
// projection players missing after both authoritative feeds are merged.
// These records use the existing live scoring model, not a made-up score.
weeklyPprProjections.forEach(projection => {
  const position = String(projection.position || "").toUpperCase();
  const name = String(projection.player_name || "").trim();
  const nflId = String(projection.player_id || "").trim();
  const team = normalizeLookupTeam(
    String(projection.team || "").toUpperCase()
  );
  if (!nflId || !name || !team ||
      !["QB", "RB", "WR", "TE"].includes(position)) return;

  const existing = players.some(player =>
    [player.id, player.nflId].filter(Boolean)
      .some(id => String(id) === nflId) ||
    (normalizeLookupName(player.name) === normalizeLookupName(name) &&
     player.position === position &&
     normalizeLookupTeam(player.team) === team)
  );
  if (existing) return;

  players.push({
    id: nflId,
    nflId,
    name,
    position,
    team,
    status: String(projection.roster_status || "UNKNOWN"),
    injuryStatus: projection.injury_status || null,
    injuryStartDate: null,
    practiceParticipation: null,
    depthChartPosition: null,
    depthChartOrder: null,
    age: null,
    yearsExp: null,
    number: null,
    backendAdded: true,
    projectionAdded: true
  });
});

players.sort((a, b) => {
  if (a.position !== b.position) {
    return (
      positionOrder[a.position] -
      positionOrder[b.position]
    );
  }

  return a.name.localeCompare(
    b.name
  );
});

console.log(
  "Frontend player universe:",
  {
    totalPlayers: players.length,
    backendScoredPlayers:
      Object.keys(
        fantasyAiScores
      ).length,
    backendAddedPlayers:
      players.filter(
        player => player.backendAdded
      ).length
  }
);
    populatePlayerSelectors();
    
    setupPlayerSearch(playerASearch, playerAResults, playerASelect);
    setupPlayerSearch(playerBSearch, playerBResults, playerBSelect);
    setupPlayerSearch(playerCSearch, playerCResults, playerCSelect);

    if (players.length >= 2) {
      playerASelect.value =
        players.find((player) => player.name === "Puka Nacua")?.id ||
        players[0].id;

      playerBSelect.value =
        players.find((player) => player.name === "Christian Watson")?.id ||
        players[1].id;

      
      playerCSelect.value =
        players.find((player) => player.name === "Ja'Marr Chase")?.id ||
        players[2].id;

      const defaultA = getPlayer(playerASelect.value);
      const defaultB = getPlayer(playerBSelect.value);
      const defaultC = getPlayer(playerCSelect.value);


      if (defaultA) {
        playerASearch.value =
          `${defaultA.name} — ${defaultA.position} — ${defaultA.team}`;
      }

      if (defaultB) {
        playerBSearch.value =
          `${defaultB.name} — ${defaultB.position} — ${defaultB.team}`;
      }

      if (defaultC) {
        playerCSearch.value =
          `${defaultC.name} — ${defaultC.position} — ${defaultC.team}`;
      }

    }
  } catch (error) {
    console.error("NFL player loading error:", error);

    resultsContainer.innerHTML = `
      <div class="result-card">
        <h3>Unable to load NFL players</h3>
        <p>The live NFL player database could not be reached.</p>
      </div>
    `;
  }

}

async function refreshPlayerInjuries() {

  try {
    const positions = ["QB", "RB", "WR", "TE"];

    const responses = await Promise.all(
      positions.map(async (position) => {
        const response = await fetch(
          `https://api.sleeper.app/v1/players/nfl?position=${position}&active=true`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          throw new Error(`Injury refresh failed: ${position}`);
        }

        return response.json();
      })
    );

    const updates = new Map();

    responses.forEach((playerMap) => {
      Object.values(playerMap).forEach((player) => {
        if (player.player_id) {
          updates.set(String(player.player_id), player);
        }
      });
    });

    sleeperInjuryFetchedAt = Date.now();
    players.forEach((player) => {
      const latest = updates.get(String(player.id));
      if (!latest) return;

      player.status = latest.status || "Unknown";
      player.injuryStatus = latest.injury_status || null;
      player.practiceParticipation =
        latest.practice_participation || null;
      player.depthChartPosition =
        latest.depth_chart_position ?? null;
      player.depthChartOrder =
        latest.depth_chart_order ?? null;
    });

    clearRankingCaches();
    renderPositionRankings();

    if (resultsContainer.querySelector(".comparison-results")) {
      comparePlayers();
    }

    console.log("Player injury statuses refreshed.");
  } catch (error) {
    console.error("Injury refresh failed:", error);
  }
}


function populatePlayerSelectors() {
  playerASelect.innerHTML = "";
  playerBSelect.innerHTML = "";
  playerCSelect.innerHTML = "";

  players.forEach((player) => {
    const label = `${player.name} — ${player.position} — ${player.team}`;

    const optionA = document.createElement("option");
    optionA.value = player.id;
    optionA.textContent = label;

    const optionB = document.createElement("option");
    optionB.value = player.id;
    optionB.textContent = label;

    const optionC = document.createElement("option");
    optionC.value = player.id;
    optionC.textContent = label;

    playerASelect.appendChild(optionA);
    playerBSelect.appendChild(optionB);
    playerCSelect.appendChild(optionC);
  });

  if (players.length > 2) {
    playerASelect.value = players[0].id;
    playerBSelect.value = players[1].id;
    playerCSelect.value = players[2].id;
  }
}


function getPlayer(id) {
  return players.find((player) => player.id === id);
}

function calculatePlayerRisk(player) {
  let risk = 5;

  const injury = (player.injuryStatus || "").toLowerCase();
  const practice = (player.practiceParticipation || "").toLowerCase();
  const status = (player.status || "").toLowerCase();

  // Injury designation
  if (injury.includes("out")) {
    risk += 75;
  } else if (injury.includes("doubtful")) {
    risk += 60;
  } else if (injury.includes("questionable")) {
    risk += 30;
  } else if (injury.includes("probable")) {
    risk += 8;
  }

  // Practice participation
  if (
    practice.includes("did not participate") ||
    practice.includes("dnp")
  ) {
    risk += 25;
  } else if (practice.includes("limited")) {
    risk += 12;
  } else if (practice.includes("full")) {
    risk -= 3;
  }

  // Active roster status
  if (
    status.includes("inactive") ||
    status.includes("reserve") ||
    status.includes("suspended")
  ) {
    risk += 35;
  }

  // Depth-chart role
  if (player.depthChartOrder) {
    if (player.depthChartOrder >= 4) {
      risk += 25;
    } else if (player.depthChartOrder === 3) {
      risk += 16;
    } else if (player.depthChartOrder === 2) {
      risk += 8;
    } else if (player.depthChartOrder === 1) {
      risk -= 3;
    }
  }

  // Experience uncertainty
  if (player.yearsExp !== null && player.yearsExp !== undefined) {
    if (player.yearsExp === 0) {
      risk += 8;
    } else if (player.yearsExp === 1) {
      risk += 4;
    }
  }

  // Age-based availability risk
  if (player.age) {
    if (player.age >= 33) {
      risk += 8;
    } else if (player.age >= 30) {
      risk += 4;
    }
  }

  return Math.max(0, Math.min(100, Math.round(risk)));
}
function getScoringEnvironment(player) {
  if (!player || !player.team) {
    return null;
  }

  const normalizeTeam = team =>
    ({
      LA: "LAR",
      JAC: "JAX",
      WSH: "WAS"
    })[team] || team;

  const team = normalizeTeam(player.team);

  const record =
    currentScoringEnvironment[team] ||
    currentScoringEnvironment[player.team];

  if (
    !record ||
    record.available !== true
  ) {
    return null;
  }

  const nextGame =
    teamNextOpponent[team] ||
    teamNextOpponent[player.team];

  if (
    nextGame?.opponent &&
    normalizeTeam(record.opponent) !==
      normalizeTeam(nextGame.opponent)
  ) {
    return null;
  }

  if (
    nextGame?.week &&
    record.week &&
    Number(record.week) !==
      Number(nextGame.week)
  ) {
    return null;
  }

  const score =
    Number(record.score);

  const impliedTeamTotal =
    Number(record.implied_team_total);

  const gameTotal =
    Number(record.game_total);

  const spread =
    Number(record.spread_line);

  if (!Number.isFinite(score)) {
    return null;
  }

  return {
    score: Math.max(
      0,
      Math.min(100, score)
    ),

    impliedTeamTotal:
      Number.isFinite(impliedTeamTotal)
        ? impliedTeamTotal
        : null,

    gameTotal:
      Number.isFinite(gameTotal)
        ? gameTotal
        : null,

    spread:
      Number.isFinite(spread)
        ? spread
        : null,

    opponent:
      record.opponent || null,

    week:
      Number(record.week) || null,

    source:
      record.source || "unknown"
  };
}

function calculateScoringEnvironmentScore(player) {
  const environment =
    getScoringEnvironment(player);

  return environment
    ? environment.score
    : 50;
}
const playerMetricsCache = new Map();

function getMetrics(player) {
  if (playerMetricsCache.has(player.id)) {
    return playerMetricsCache.get(player.id);
  }

  const production =
    calculateProductionScore(player);

  const usage =
    calculateUsageScore(player);

  const opportunity =
    calculateOpportunityScore(player);

  const matchup =
    calculateMatchupScore(player);

  const playCallerMatchup =
    calculatePlayCallerMatchupScore(player);

  const playerVsDefensiveCaller =
    calculatePlayerVsDefensiveCallerScore(player);

  const redzone =
    calculateRedZoneScore(player);

  const expert =
    calculateModelConfidence(player);

  const risk =
    calculatePlayerRisk(player);

  const scoringEnvironment =
    calculateScoringEnvironmentScore(player);

  const metrics = {
    opportunity,
    production,
    usage,
    matchup,
    playCallerMatchup,
    playerVsDefensiveCaller,
    redzone,
    expert,
    risk,
    scoringEnvironment
  };
 
  playerMetricsCache.set(player.id, metrics);

  return metrics;
}

function getTrenchMatchup(player) {


  const matchup = teamNextOpponent[player.team];
  const opponent = matchup?.opponent;

  if (!opponent) return null;

  const normalize = team =>
    team === "LAR" ? "LA" : team;

  const record =
    currentTrenchSignals[player.team] ||
    currentTrenchSignals[normalize(player.team)] ||
    currentTrenchSignals[player.team === "LA" ? "LAR" : player.team];

  if (
    !record ||
    normalize(record.defense_team) !== normalize(opponent) ||
    record.available !== true
  ) {
    return null;
  }

  if (
    trenchSignalWeek !== null &&
    snapshotWeek &&
    Number(trenchSignalWeek) !== Number(snapshotWeek)
  ) {
    return null;
  }

  const pass = Number(record.pass_score);
  const run = Number(record.run_score);

  if (![pass, run].every(Number.isFinite)) {
    return null;
  }

  const score =
    player.position === "RB"
      ? run
      : player.position === "TE"
        ? (pass + run) / 2
        : pass;

  return {
    score: Math.max(0, Math.min(100, score)),
    confidence: record.confidence || "team_metrics_only",
    injuryAdjusted: record.injury_adjusted === true,

    opponent: record.defense_team,
    passScore: pass,
    runScore: run,
    offensiveLineGrade: record.offensive_line_grade ?? record.offense_line_grade ?? null,
    defensiveLineGrade: record.defensive_line_grade ?? record.defense_front_grade ?? null,
    offenseSackRate: record.offense_sack_rate ?? null,
    offenseQbHitRate: record.offense_qb_hit_rate ?? null,
    offenseRushSuccessRate: record.offense_rush_success_rate ?? null,
    defenseSackRate: record.defense_sack_rate ?? null,
    defenseQbHitRate: record.defense_qb_hit_rate ?? null,
    defenseRunStopRate: record.defense_run_stop_rate ?? null,
    rateSource: record.rate_source ?? null
  };
}
function isPlayerMatchupCompleted(player) {
  if (!player || !player.team) {
    return false;
  }

  const normalize = team =>
    team === "LAR" ? "LA" : team;

  const matchup =
    teamNextOpponent[player.team] ||
    teamNextOpponent[normalize(player.team)];

  if (!matchup || !matchup.week) {
    return false;
  }

  return weeklyStats.some(row =>
    Number(row.season) === 2026 &&
    Number(row.week) === Number(matchup.week) &&
    normalize(row.team) === normalize(player.team)
  );
}

function calculateScore(player, profile) {
  const metrics = getMetrics(player);
  const weights = riskProfiles[profile] || BASE_WEIGHTS;
  const trench = getTrenchMatchup(player);
  const scoringEnvironment =
    getScoringEnvironment(player);
  const trenchWeight =
    trench ? 0.07 : 0;

  const scoringEnvironmentWeight =
    scoringEnvironment ? 0.07 : 0;

  const originalWeightScale =
    1 -
    trenchWeight -
    scoringEnvironmentWeight;

  const baseScore =
    metrics.opportunity * weights.opportunity +
    metrics.production * weights.production +
    metrics.usage * weights.usage +
    metrics.playCallerMatchup * weights.playCallerMatchup +
    metrics.playerVsDefensiveCaller * weights.playerVsDefensiveCaller +
    metrics.redzone * weights.redzone +
    metrics.matchup * weights.matchup +
    metrics.expert * weights.expert +
    (100 - metrics.risk) * weights.risk;

  const originalWeightTotal =
    weights.opportunity +
    weights.production +
    weights.usage +
    weights.playCallerMatchup +
    weights.playerVsDefensiveCaller +
    weights.redzone +
    weights.matchup +
    weights.expert +
    weights.risk;

  const normalizedBaseScore =
    baseScore / originalWeightTotal;

 
  const score =
    normalizedBaseScore *
      originalWeightScale +
    (trench
      ? trench.score * trenchWeight
      : 0) +
    (scoringEnvironment
      ? scoringEnvironment.score *
        scoringEnvironmentWeight
      : 0);

  const injury = String(player.injuryStatus || "")
    .trim()
    .toUpperCase();

  const rosterStatus = String(player.status || "")
    .trim()
    .toUpperCase();

  const isUnavailable =
    [
      "OUT",
      "IR",
      "INJURED_RESERVE",
      "PUP",
      "EXEMPT"
    ].includes(injury) ||
    [
      "INACTIVE",
      "INJURED_RESERVE",
      "IR",
      "SUSPENDED",
      "PUP",
      "EXEMPT",
      "EXEMPT_LIST",
      "RESERVE/EXEMPT",
      "RESERVE_EXEMPT"
    ].includes(rosterStatus);
  const injuryBoost =
    !snapshotWeek && !isUnavailable
      ? calculateInjuryOpportunityBoost(player)
      : 0;

  // Sleeper IDs and GSIS IDs belong to different namespaces.
  // Prefer an exact backend score key, then reconcile by player identity.
  // Never let a synthetic projection ID prevent a valid rookie prior.
  const backendScoreId = [player.nflId, player.id]
    .filter(Boolean)
    .map(id => String(id))
    .find(id => fantasyAiScores[id] != null);
  const matchedBackendId = Object.entries(nflPlayerLookup).find(
    ([id, nfl]) => {
      const normalizeTeam = value =>
        ({ LA: "LAR", JAC: "JAX", WSH: "WAS" })[
          String(value || "").toUpperCase()
        ] || String(value || "").toUpperCase();
      return (
        normalizeName(player.name) === normalizeName(nfl.name) &&
        String(player.position || "").toUpperCase() ===
          String(nfl.position || "").toUpperCase() &&
        normalizeTeam(player.team) === normalizeTeam(nfl.team) &&
        fantasyAiScores[id] != null
      );
    }
  )?.[0];
  const rookieScore = fantasyAiScores[
    backendScoreId || matchedBackendId
  ] || null;
 
  const rookieAdjustment =
    rookieScore?.rookie_prior_adjustment;

  const useRookiePrior =
    rookieScore?.available === true &&
    rookieAdjustment?.eligible === true &&
    rookieAdjustment?.applied === true &&
    Number.isFinite(rookieAdjustment.prior_score) &&
    Number.isFinite(rookieAdjustment.weight) &&
    rookieAdjustment.weight > 0;

  const scoringBase = useRookiePrior
    ? (
        score * (1 - rookieAdjustment.weight) +
        rookieAdjustment.prior_score * rookieAdjustment.weight
      )
    : score;

  const adjustedScore = Math.min(
    100,
    scoringBase + injuryBoost
  );

  // Targeted read-only audit: show precisely why Emmanuel Wilson ranks high.
  // No changes to scoring, weights, or published rankings.
  if ((String(player.id) === "11435" ||
       String(player.nflId || "") === "00-0038797") &&
      !window.__dataDaddyWilsonAuditLogged) {
    window.__dataDaddyWilsonAuditLogged = true;
    console.group("DATA DADDY AI SCORE AUDIT — Emmanuel Wilson");
    console.table({
      opportunity: { score: metrics.opportunity, weight: weights.opportunity },
      production: { score: metrics.production, weight: weights.production },
      usage: { score: metrics.usage, weight: weights.usage },
      redzone: { score: metrics.redzone, weight: weights.redzone },
      matchup: { score: metrics.matchup, weight: weights.matchup },
      playCallerMatchup: { score: metrics.playCallerMatchup, weight: weights.playCallerMatchup },
      playerVsDefensiveCaller: { score: metrics.playerVsDefensiveCaller, weight: weights.playerVsDefensiveCaller },
      expert: { score: metrics.expert, weight: weights.expert },
      risk: { score: metrics.risk, weight: weights.risk }
    });
    console.log("Additional adjustments", {
      profile, team: player.team, position: player.position,
      trench, scoringEnvironment, injuryStatus: player.injuryStatus,
      rosterStatus: player.status, injuryBoost,
      rookieAdjustment: useRookiePrior ? rookieAdjustment : null,
      healthySeasonGames: getProductionGameCount(player),
      finalScore: Number(adjustedScore.toFixed(1))
    });
    console.groupEnd();
  }

  // Read-only Week 7 TE signal audit. Never changes player rankings.
  if (
    player.position === "TE" &&
    ["Travis Kelce", "Juwan Johnson", "Jake Ferguson",
     "Kenyon Sadiq", "Cade Otton", "Tyler Higbee"].includes(player.name) &&
    typeof window !== "undefined"
  ) {
    window.__dataDaddyTeAuditLogged ||= new Set();
    const auditKey = [player.name, profile, snapshotWeek || "live"].join("|");
    if (!window.__dataDaddyTeAuditLogged.has(auditKey)) {
      window.__dataDaddyTeAuditLogged.add(auditKey);
      const recentRows = getPlayerWeeklyStats(player)
        .filter(game => Number(game.season) === 2026)
        .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
        .slice(0, 3);
      const recentTargets = recentRows.map(game => ({
        week: game.week, team: game.team,
        name: game.player_display_name || game.player_name || game.name,
        targets: Number(game.targets || 0),
        carries: Number(game.carries || game.rushing_attempts || 0),
        receptions: Number(game.receptions || 0),
        receivingYards: Number(game.receiving_yards || 0)
      }));
      console.group("DATA DADDY WEEK 7 TE SIGNAL AUDIT — " + player.name);
      console.table({
        opportunity: {score: metrics.opportunity, weight: weights.opportunity},
        production: {score: metrics.production, weight: weights.production},
        usage: {score: metrics.usage, weight: weights.usage},
        redzone: {score: metrics.redzone, weight: weights.redzone},
        matchup: {score: metrics.matchup, weight: weights.matchup},
        playCallerMatchup: {score: metrics.playCallerMatchup, weight: weights.playCallerMatchup},
        playerVsDefensiveCaller: {score: metrics.playerVsDefensiveCaller, weight: weights.playerVsDefensiveCaller},
        expert: {score: metrics.expert, weight: weights.expert},
        risk: {score: metrics.risk, weight: weights.risk}
      });
      console.table(recentTargets);
      console.log("Matching and adjustments", {
        playerId: player.id, nflId: player.nflId, team: player.team,
        recentMatchedGames: recentRows.length,
        opportunityFallback20: metrics.opportunity === 20,
        noMatched2026Games: recentRows.length === 0,
        trench, scoringEnvironment, injuryBoost,
        rookieAdjustment: useRookiePrior ? rookieAdjustment : null,
        finalAiScore: Number(adjustedScore.toFixed(1))
      });
      console.groupEnd();
    }
  }

  return Number(adjustedScore.toFixed(1));
}

const injuryOpportunityCache = new Map();
const injuryOpportunityDetailsCache = new Map();
const rankingCache = {};

function clearRankingCaches() {
  Object.keys(rankingCache).forEach((key) => {
    delete rankingCache[key];
  });


  playerMetricsCache.clear();
  injuryOpportunityCache.clear();
  injuryOpportunityDetailsCache.clear();
}

function calculateInjuryOpportunityBoost(player) {
  if (!player || !player.team || snapshotWeek) return 0;

  const injury = String(player.injuryStatus || "")
    .trim().toUpperCase();

  const rosterStatus = String(player.status || "")
    .trim().toUpperCase();

  const unavailable =
    ["OUT", "IR", "PUP"].includes(injury) ||
    ["INACTIVE", "IR", "INJURED_RESERVE", "PUP",
      "SUSPENDED"].includes(rosterStatus);

  if (unavailable) return 0;

  if (injuryOpportunityCache.has(player.id)) {
    return injuryOpportunityCache.get(player.id);
  }

  const teammates = players.filter((teammate) =>
    teammate.team === player.team &&
    teammate.id !== player.id
  );

  let boost = 0;
  const details = [];

  teammates.forEach((absentPlayer) => {

    const teammateInjury = String(
      absentPlayer.injuryStatus || ""
    ).trim().toUpperCase();

    const teammateStatus = String(
      absentPlayer.status || ""
    ).trim().toUpperCase();

    const fullyUnavailable =
      ["OUT", "IR", "PUP"].includes(teammateInjury) ||
      ["INACTIVE", "IR", "INJURED_RESERVE", "PUP",
        "SUSPENDED"].includes(teammateStatus);

    const multiplier = fullyUnavailable
      ? 1
      : teammateInjury === "DOUBTFUL"
        ? 0.5
        : 0;

    if (multiplier === 0) return;

    const recentGames = [
      ...getPlayerWeeklyStats(absentPlayer)
    ]
      .sort((a, b) =>
        Number(b.season) - Number(a.season) ||
        Number(b.week) - Number(a.week)
      )
      .slice(0, 4);

    const averageOpportunities = recentGames.length
      ? recentGames.reduce((total, game) =>
          total +
          Number(game.targets || 0) +
          Number(game.carries || 0) +
          (absentPlayer.position === "QB"
            ? Number(game.attempts || 0)
            : 0),
        0) / recentGames.length
      : 0;

    const significantRole =
      averageOpportunities >= 8 ||
      Number(absentPlayer.depthChartOrder) === 1;

    if (!significantRole) return;

    let contribution = 0;

    if (
      absentPlayer.position === "RB" &&
      player.position === "RB"
    ) {
      contribution += (
        Number(player.depthChartOrder) === 2 ? 6 : 3
      ) * multiplier;
    }

    if (
      ["WR", "TE"].includes(absentPlayer.position) &&
      ["WR", "TE"].includes(player.position)
    ) {
      contribution += 3 * multiplier;
    }

    // Respect the existing eight-point total cap.
    const appliedContribution = Math.min(
      contribution,
      Math.max(0, 8 - boost)
    );

    if (appliedContribution <= 0) return;

    boost += appliedContribution;

    details.push({
      name: absentPlayer.name,
      status: teammateInjury ||
        teammateStatus ||
        "UNAVAILABLE",
      points: Number(appliedContribution.toFixed(1)),
      provisional: multiplier === 0.5
    });
  });

  boost = Number(Math.min(8, boost).toFixed(1));

  injuryOpportunityDetailsCache.set(player.id, details);
  injuryOpportunityCache.set(player.id, boost);

  return boost;

}


// Registered at script load, not inside a rankings cache miss.
// Read-only workload comparison: uses completed 2026 games, not projected
// depth-chart roles. It does not change any AI score.
window.dataDaddyAuditWilsonWorkload = function () {
  const wilson = players.find((p) =>
    String(p.id) === "11435" || String(p.nflId || "") === "00-0038797"
  );
  if (!wilson) {
    console.warn("Wilson workload audit: SEA RB not found");
    return;
  }
  const games = getPlayerWeeklyStats(wilson)
    .filter((g) => Number(g.season) === 2026 && g.team === "SEA")
    .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
    .slice(0, 5);
  const records = games.map((g) => {
    const teamRows = getTeamGameRows(Number(g.season), Number(g.week), "SEA");
    const carries = (row) => Number(row.carries ?? row.rushing_attempts ?? 0);
    const targets = (row) => Number(row.targets ?? 0);
    const teamCarries = teamRows.reduce((sum, row) => sum + carries(row), 0);
    const teamTargets = teamRows.reduce((sum, row) => sum + targets(row), 0);
    const teammates = teamRows.filter((row) => row.position === "RB")
      .map((row) => ({
        name: row.player_display_name || row.player_name,
        carries: carries(row), targets: targets(row)
      })).sort((a, b) => b.carries + b.targets - a.carries - a.targets);
    return {
      week: g.week, wilsonCarries: carries(g), wilsonTargets: targets(g),
      wilsonRushYards: Number(g.rushing_yards || 0),
      wilsonRecYards: Number(g.receiving_yards || 0),
      teamCarries, teamTargets,
      carrySharePct: teamCarries ? +(100 * carries(g) / teamCarries).toFixed(1) : null,
      targetSharePct: teamTargets ? +(100 * targets(g) / teamTargets).toFixed(1) : null,
      teammates
    };
  });
  console.group("DATA DADDY — Emanuel Wilson workload vs SEA RBs");
  console.table(records.map(({ teammates, ...row }) => row));
  records.forEach((row) => console.log("Week " + row.week + " SEA RB workload", row.teammates));
  console.groupEnd();
  return records;
};

// Shadow-only Week 7 return-to-play role scenarios. These do not alter
// live rankings, weights, or player availability.
window.dataDaddyWilsonRoleSecurityTest = function () {
  const wilson = players.find((p) =>
    String(p.id) === "11435" || String(p.nflId || "") === "00-0038797"
  );
  if (!wilson) {
    console.warn("Role-security test: Emanuel Wilson not loaded");
    return [];
  }
  const base = calculateScore(wilson, "balanced");
  const metrics = getMetrics(wilson);
  const games = getPlayerWeeklyStats(wilson)
    .filter((g) => Number(g.season) === 2026 && g.team === "SEA")
    .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
    .slice(0, 3);
  const carries = (g) => Number(g.carries ?? g.rushing_attempts ?? 0);
  const avg = (rows, fn) => rows.length
    ? rows.reduce((sum, row) => sum + fn(row), 0) / rows.length : 0;
  const recentCarries = avg(games, carries);
  const recentTargets = avg(games, (g) => Number(g.targets || 0));
  const scenarioRows = [
    { scenario: "Charbonnet out — lead committee", workloadRetention: 1.00 },
    { scenario: "Charbonnet active — limited", workloadRetention: 0.75 },
    { scenario: "Charbonnet active — meaningful role", workloadRetention: 0.50 },
    { scenario: "Multiple backs return — crowded backfield", workloadRetention: 0.35 }
  ];
  // Hypothetical sensitivity test, not a calibrated predictive model.
  // Apply only the proportional loss in Opportunity and Usage contribution.
  const rows = scenarioRows.map((row) => {
    const reduction = (1 - row.workloadRetention) *
      ((Number(metrics.opportunity) || 0) * BASE_WEIGHTS.opportunity +
       (Number(metrics.usage) || 0) * BASE_WEIGHTS.usage);
    return {
      scenario: row.scenario,
      retainedWorkloadPct: Math.round(row.workloadRetention * 100),
      expectedCarries: +(recentCarries * row.workloadRetention).toFixed(1),
      expectedTargets: +(recentTargets * row.workloadRetention).toFixed(1),
      baselineAiScore: base,
      shadowAiScore: +Math.max(0, base - reduction).toFixed(1),
      scoreDelta: +(-reduction).toFixed(1)
    };
  });
  console.group("DATA DADDY — Emanuel Wilson role-security SHADOW TEST");
  console.log("Historical workload:", {
    recentGames: games.map((g) => g.week),
    averageCarries: +recentCarries.toFixed(1),
    averageTargets: +recentTargets.toFixed(1),
    opportunity: metrics.opportunity, usage: metrics.usage,
    matchup: metrics.matchup
  });
  console.table(rows);
  console.log("Scenario assumptions are illustrative, not verified player projections. Live AI scores unchanged.");
  console.groupEnd();
  return rows;
};

// League-wide read-only role-security sensitivity audit.
// Hypothetical reductions only: no injury return is assumed confirmed.
// Published rankings, AI scores and PPR projections remain unchanged.
window.dataDaddyRbRoleSecurityAudit = function () {
  const rbs = players.filter((p) => p.position === "RB");
  const rows = rbs.map((p) => {
    const games = getPlayerWeeklyStats(p)
      .filter((g) => Number(g.season) === 2026 &&
        String(g.team) === String(p.team))
      .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
      .slice(0, 3);
    if (!games.length) return null;
    const average = (fn) => games.reduce((sum, g) => sum + fn(g), 0) / games.length;
    const avgCarries = average((g) => Number(g.carries ?? g.rushing_attempts ?? 0));
    const avgTargets = average((g) => Number(g.targets || 0));
    if (avgCarries + avgTargets < 4) return null;
    const metrics = getMetrics(p);
    const base = calculateScore(p, "balanced");
    const relevantTeammates = rbs.filter((mate) =>
      mate.id !== p.id && mate.team === p.team &&
      (mate.depthChartOrder == null || Number(mate.depthChartOrder) <= 3)
    );
    const teammateStatus = relevantTeammates.map((mate) => ({
      name: mate.name, depth: mate.depthChartOrder,
      injury: mate.injuryStatus, status: mate.status,
      practice: mate.practiceParticipation
    }));
    const sensitivity = (retention) => {
      const reduction = (1 - retention) * (
        (Number(metrics.opportunity) || 0) * BASE_WEIGHTS.opportunity +
        (Number(metrics.usage) || 0) * BASE_WEIGHTS.usage
      );
      return +Math.max(0, base - reduction).toFixed(1);
    };
    return {
      name: p.name, team: p.team, games: games.length,
      avgCarries: +avgCarries.toFixed(1), avgTargets: +avgTargets.toFixed(1),
      baseline: base, shadow75: sensitivity(0.75),
      shadow50: sensitivity(0.50),
      opportunity: metrics.opportunity, usage: metrics.usage,
      teammateCount: teammateStatus.length,
      teammates: teammateStatus
    };
  }).filter(Boolean).sort((a, b) => b.baseline - a.baseline);
  console.group("DATA DADDY — RB role-security league-wide SHADOW AUDIT");
  console.log("Hypothetical 75% and 50% workload retention. Not injury confirmations or calibrated forecasts.");
  console.table(rows.map(({ teammates, ...row }) => row));
  console.log("Individual teammate injury/depth records available in returned rows.");
  console.groupEnd();
  return rows;
};

// Historical teammate-return candidates, for review only. A current
// roster status is NOT proof that a player will be active on game day.
window.dataDaddyRbReturnCandidates = function (teamFilter = "SEA") {
  const team = String(teamFilter || "SEA").toUpperCase();
  const teamRbs = players.filter((p) => p.position === "RB" && p.team === team);
  const rows = teamRbs.map((p) => {
    const games = getPlayerWeeklyStats(p)
      .filter((g) => Number(g.season) === 2026 && g.team === team)
      .sort((a, b) => Number(b.week || 0) - Number(a.week || 0));
    const recent = games.slice(0, 3);
    const latestWeek = games.length ? Number(games[0].week) : null;
    const completedWeeks = weeklyStats
      .filter((g) => Number(g.season) === 2026 && g.team === team)
      .reduce((max, g) => Math.max(max, Number(g.week || 0)), 0);
    const avg = (items, field) => items.length
      ? +(items.reduce((sum, g) => sum +
          Number(field === "carries" ? (g.carries ?? g.rushing_attempts ?? 0) : (g.targets ?? 0)), 0) /
          items.length).toFixed(1) : null;
    const gap = latestWeek == null ? null : Math.max(0, completedWeeks - latestWeek);
    const status = String(p.injuryStatus || p.status || "").toUpperCase();
    const missingRecent = gap != null && gap >= 1;
    const hadRole = games.some((g) =>
      Number(g.carries ?? g.rushing_attempts ?? 0) + Number(g.targets || 0) >= 8
    );
    return {
      name: p.name, team, id: p.id, depth: p.depthChartOrder,
      latestPlayedWeek: latestWeek, latestTeamWeek: completedWeeks,
      missedTeamWeeks: gap, recentCarries: avg(recent, "carries"),
      recentTargets: avg(recent, "targets"),
      injury: p.injuryStatus || "", rosterStatus: p.status || "",
      practice: p.practiceParticipation || "",
      candidate: Boolean(missingRecent && hadRole),
      confirmation: "UNVERIFIED — requires fresh active/returning evidence"
    };
  }).sort((a, b) => Number(b.candidate) - Number(a.candidate) ||
    (a.depth ?? 99) - (b.depth ?? 99));
  console.group("DATA DADDY — " + team + " RB historical return candidates");
  console.log("Missing games and historical role are flags only. Never apply a score penalty without verified availability and role evidence.");
  console.table(rows);
  console.groupEnd();
  return rows;
};

// Read-only historical-vs-recent RB role-change audit.
// Recent = last three completed team weeks; prior = up to three earlier
// games. Missing games count as zero only in the recent team-week window.
window.dataDaddyRbRoleChangeAudit = function (teamFilter = "SEA") {
  const team = String(teamFilter || "SEA").toUpperCase();
  const teamRows = weeklyStats.filter((g) =>
    Number(g.season) === 2026 && g.team === team);
  const weeks = [...new Set(teamRows.map((g) => Number(g.week))
    .filter(Number.isFinite))].sort((a, b) => b - a);
  const recentWeeks = weeks.slice(0, 3);
  const priorWeeks = weeks.slice(3, 6);
  const rbPlayers = players.filter((p) => p.position === "RB" && p.team === team);
  const workload = (player, windowWeeks) => {
    if (!windowWeeks.length) return null;
    const games = getPlayerWeeklyStats(player).filter((g) =>
      Number(g.season) === 2026 && g.team === team &&
      windowWeeks.includes(Number(g.week)));
    const sum = (fn) => games.reduce((total, g) => total + fn(g), 0);
    const carries = sum((g) => Number(g.carries ?? g.rushing_attempts ?? 0));
    const targets = sum((g) => Number(g.targets || 0));
    return {
      carries: +(carries / windowWeeks.length).toFixed(1),
      targets: +(targets / windowWeeks.length).toFixed(1),
      opportunities: +((carries + targets) / windowWeeks.length).toFixed(1),
      played: games.length
    };
  };
  const rows = rbPlayers.map((p) => {
    const recent = workload(p, recentWeeks);
    const prior = workload(p, priorWeeks);
    const delta = recent && prior
      ? +(recent.opportunities - prior.opportunities).toFixed(1) : null;
    const priorMeaningful = prior && prior.opportunities >= 6;
    const recentDecline = delta != null && delta <= -3;
    const recentRise = delta != null && delta >= 3;
    return {
      name: p.name, id: p.id, team, depth: p.depthChartOrder,
      recentWeeks: recentWeeks.join(","), priorWeeks: priorWeeks.join(","),
      priorOppPerWeek: prior?.opportunities ?? null,
      recentOppPerWeek: recent?.opportunities ?? null,
      priorGamesPlayed: prior?.played ?? null,
      recentGamesPlayed: recent?.played ?? null,
      oppDelta: delta,
      roleTrend: !prior ? "INSUFFICIENT PRIOR DATA" :
        recentDecline && priorMeaningful ? "DECLINING / RETURN CANDIDATE" :
        recentRise ? "INCREASING" : "NO CLEAR CHANGE",
      injury: p.injuryStatus || "", rosterStatus: p.status || "",
      practice: p.practiceParticipation || "",
      verifiedReturn: false
    };
  }).sort((a, b) => (a.oppDelta ?? 999) - (b.oppDelta ?? 999));
  console.group("DATA DADDY — " + team + " RB role change (historical vs recent)");
  console.log("Historical trend only; not proof of injury return or future workload. No live scoring changes.");
  console.table(rows);
  console.groupEnd();
  return rows;
};

window.dataDaddyAuditWilson = function () {
  const matches = players.filter((p) =>
    String(p.id) === "11435" ||
    String(p.nflId || "") === "00-0038797" ||
    (p.position === "RB" && p.team === "SEA" &&
      normalizeName(p.name) === normalizeName("Emanuel Wilson"))
  );
  if (!matches.length) {
    console.warn("WILSON AUDIT: Emmanuel Wilson not found in loaded player universe. Check whether players have finished loading.");
    return;
  }
  matches.forEach((p) => {
    window.__dataDaddyWilsonAuditLogged = false;
    const score = calculateScore(p, "balanced");
    console.log("WILSON AUDIT RESULT", {
      name: p.name, team: p.team, position: p.position, score,
      metrics: getMetrics(p), injuryStatus: p.injuryStatus,
      rosterStatus: p.status, depthChartOrder: p.depthChartOrder,
      seasonGames: getProductionGameCount(p)
    });
  });
};

// Single source of truth for AI Scores displayed in Rankings and Projections.
// Weekly PPR snapshot model_score is historical metadata, not a live display score.
function getDisplayedAiScore(player, profile) {
  if (!player) return NaN;
  const liveScore = calculateScore(player, profile);
  const projection = getPlayerPprProjection(player);
  const adjustedScore = Number(projection?.model_score);
  const originalScore = Number(projection?.original_model_score);
  const weekMatches = Number(projection?.snapshot_week) ===
    Number(document.documentElement.dataset.targetWeek);
  // Apply only the analyst's delta to the live AI score. This keeps
  // the live 11-signal model and profile weighting intact for everyone.
  if (weekMatches && Number.isFinite(adjustedScore) &&
      Number.isFinite(originalScore) && adjustedScore !== originalScore) {
    return Math.round((liveScore + adjustedScore - originalScore) * 100) / 100;
  }
  return liveScore;
}

// A weekly projection may have a valid frozen model score even when
// the live roster feed has not resolved its player ID/name yet.
// Use it only for unresolved players; never mix snapshot and live
// scores for successfully matched players.
function getProjectionAiScore(projection, player, profile) {
  if (player) return getDisplayedAiScore(player, profile);
  const snapshotScore = Number(projection?.model_score);
  return Number.isFinite(snapshotScore) &&
    snapshotScore >= 0 && snapshotScore <= 100
      ? snapshotScore
      : NaN;
}

function getPositionRankings(position, profile) {
  const cacheKey = `${profile}-${position}`;

  if (rankingCache[cacheKey]) {
    return rankingCache[cacheKey];
  }
const relevantPlayers = players.filter((player) => {
  if (player.position !== position) {
    return false;
  }
  // Week 8 editorial exclusion: these players must not appear
  // in the WR AI rankings. Keep model scores and PPR data untouched.
  if (position === "WR" && [
    "velus jones", "zay jones", "donte thornton"
  ].includes(normalizeName(player.name))) {
    return false;
  }
  if (verifiedInjuryOutIds.has(String(player.id)) ||
      verifiedInjuryOutIds.has(String(player.nflId)) ||
      verifiedInjuryOutKeys.has(
    String(player.name).trim().toLowerCase() + "|" +
    String(player.team).trim().toUpperCase()
  )) {
    return false;
  }

  // Preserve the frozen Week 3 availability override.
  if (
    snapshotWeek === "3" &&
    player.name === "Josh Jacobs"
  ) {
    return false;
  }

  const injury = String(
    player.injuryStatus || ""
  )
    .trim()
    .toUpperCase();

  const rosterStatus = String(
    player.status || ""
  )
    .trim()
    .toUpperCase();
/*
 * Only apply matchup-based eligibility when
 * matchup data matches the displayed week.
 * Missing data must not be interpreted as a bye.
 */
const playerTeam =
  String(player.team || "")
    .trim()
    .toUpperCase() === "LA"
      ? "LAR"
      : String(player.team || "")
          .trim()
          .toUpperCase();

const byeTeamsByWeek = {
  5: ["CAR", "KC"],
  6: ["CIN", "DET", "MIA", "MIN"],
  7: ["BUF", "JAX", "LAC", "WAS"],
  8: ["HOU", "NO", "NYG", "SF"],
  9: ["PIT", "TEN"],
  10: ["CHI", "DEN", "PHI", "TB"],
  11: ["ATL", "CLE", "GB", "LAR", "NE", "SEA"],
  13: ["BAL", "IND", "LV", "NYJ"],
  14: ["ARI", "DAL"]
};

const displayedWeek = Number(
  document.documentElement.dataset.targetWeek
);

const byeTeams = byeTeamsByWeek[displayedWeek] || [];

if (byeTeams.includes(playerTeam)) {
  return false;
}

const weeklyMatchup =
  teamNextOpponent[playerTeam];

const matchupWeekAligned =
  document.documentElement.dataset
    .matchupWeekAligned !== "false";

if (
  matchupWeekAligned &&
  String(weeklyMatchup?.opponent || "")
    .trim()
    .toUpperCase() === "BYE"
) {
  return false;
}

  const unavailableRosterStatuses = [
    "INACTIVE",
    "INJURED_RESERVE",
    "IR",
    "SUSPENDED",
    "PUP",
    "PHYSICALLY_UNABLE_TO_PERFORM",
    "NON_FOOTBALL_INJURY",
    "NON_FOOTBALL_ILLNESS"
  ];

 const playerIds = [
  player.nflId,
  player.id
]
  .filter(Boolean)
  .map(id => String(id));

const hasBackendModelScore =
  playerIds.some(
    id =>
      fantasyAiScores[id] !== undefined &&
      fantasyAiScores[id] !== null
  );

/*
 * The backend model determines whether a player
 * belongs in the weekly player universe.
 *
 * Confirmed unavailable players must still be
 * removed from weekly rankings and snapshots.
 * Questionable/Doubtful players remain eligible
 * so their injury risk can be reflected by the
 * model instead of deleting them completely.
 */
const confirmedUnavailable =
  injury === "OUT" ||
  injury === "PUP" ||
  injury === "IR" ||
  injury === "INJURED_RESERVE" ||
  unavailableRosterStatuses.includes(
    rosterStatus
  );

if (confirmedUnavailable) {
  return false;
}

  /*
   * The backend model is now authoritative for
   * weekly player eligibility.
   *
   * If Update NFL Stats produced a Fantasy AI
   * score for this player, keep him in rankings.
   * This prevents missing current-week veterans
   * from being removed again by Sleeper depth
   * chart or current-stat requirements.
   */
 const hasStats =
  getPlayerWeeklyStats(player).length > 0;

const depthOrder =
  Number(player.depthChartOrder || 0);

/*
 * QB is different from the other fantasy
 * positions. Only the current starting QB
 * should appear in weekly QB rankings.
 *
 * A backend model score alone must not allow
 * backup/developmental QBs to bypass the
 * depth-chart requirement.
 */
  if (position === "QB") {
    // Week 7 TB: keep the practicing/questionable expected starter.
    // Backup Jalon Daniels only becomes eligible after a confirmed
    // Mayfield OUT and a confirmed starting-QB change.
    if (displayedWeek === 7 && playerTeam === "TB") {
      if (player.name === "Baker Mayfield") return true;
      if (player.name === "Jalon Daniels") return false;
    }
    // Week 7 verified NYG starter change: Sleeper still lists
    // McCarthy third on its depth chart. Keep the verified starter
    // and exclude the benched QB until the feed catches up.
    if (displayedWeek === 7 && playerTeam === "NYG") {
      if (player.name === "J.J. McCarthy") return true;
      if (player.name === "Jameis Winston") return false;
    }
    return depthOrder === 1;
  }

  if (position === "RB") {
    return (
      (depthOrder >= 1 &&
        depthOrder <= 3) ||
      hasStats
    );
  }

  if (position === "WR") {
    return (
      (depthOrder >= 1 &&
        depthOrder <= 3) ||
      hasStats
    );
  }

  if (position === "TE") {
    // Depth-chart backups without any current-season participation
    // should not rank solely on neutral/missing-data signals.
    const currentTeGames = getPlayerWeeklyStats(player)
      .filter(game => Number(game.season) === 2026);
    // A single cameo is not evidence of a recurring receiving role.
    // Preserve TE1 eligibility; TE2/TE3 must demonstrate targets.
    const recentTeGames = currentTeGames
      .sort((a, b) => Number(b.week || 0) - Number(a.week || 0))
      .slice(0, 3);
    const recentTargets = recentTeGames.reduce(
      (sum, game) => sum + Number(game.targets || 0), 0
    );
    const targetedGames = recentTeGames.filter(
      game => Number(game.targets || 0) >= 2
    ).length;
    // A depth-chart TE1 label alone cannot justify a weekly ranking
    // when the player has no 2026 receiving involvement. This blocks
    // neutral-data placeholders from displacing productive veterans.
    // Retain a TE1 with documented 2026 involvement, even if limited.
    const hasCurrentTeInvolvement = currentTeGames.some(game =>
      Number(game.targets || 0) > 0 ||
      Number(game.receptions || 0) > 0 ||
      Number(game.receiving_yards || 0) > 0
    );
    // Week 7: Warren is OUT. Mallory returned from IR and earned
    // six targets in Week 6, so the two-game minimum would incorrectly
    // hide an active receiving TE from rankings and model snapshots.
    const malloryWeek7Role =
      displayedWeek === 7 &&
      playerTeam === "IND" &&
      normalizeName(player.name) === normalizeName("Will Mallory") &&
      recentTeGames.some(game => Number(game.week) === 6 &&
        Number(game.targets || 0) >= 6);
    return (
      malloryWeek7Role ||
      (depthOrder === 1 && hasCurrentTeInvolvement) ||
      (recentTeGames.length >= 2 &&
        targetedGames >= 2 &&
        recentTargets >= 6)
    );
  }

  return false;
});
  const rankings = relevantPlayers
    .map((player) => ({
      player,
      score: getDisplayedAiScore(player, profile)
    }))
    .sort((a, b) =>
      b.score - a.score ||
      a.player.name.localeCompare(b.player.name)
    );

  // Weekly WR eligibility must agree with the published weekly projection
  // player universe. This runs for every future week, not just Week 8.
  // Do not invent a live AI rank for a WR absent from the weekly model.
  // Players with verified rookie/injury opportunity remain eligible when
  // the weekly builder includes them. Historical snapshots stay unchanged.
  if (position === "WR" && !snapshotWeek &&
      weeklyPprProjections.some(row =>
        Number(row.snapshot_week) ===
        Number(document.documentElement.dataset.targetWeek) &&
        String(row.position).toUpperCase() === "WR")) {
    const eligible = rankings.filter(({ player }) =>
      Boolean(getPlayerPprProjection(player))
    );
    const missing = rankings.length - eligible.length;
    if (missing) {
      console.info("Weekly WR eligibility: excluded", missing,
        "players absent from published weekly projection universe");
    }
    rankings.splice(0, rankings.length, ...eligible);
  }

  // Week 8 editorial role eligibility: these seven receivers have
  // verified low-information fallback profiles in the published audit.
  // Apply the rule to the live AI rankings independently of CSV loading,
  // because this tab ranks its own live player pool.
  if (position === "WR") {
    const flaggedIds = new Set([
      "7746", "8013", "11474", "11306", "12732", "8076", "12520"
    ]);
    const flaggedNames = new Set([
      "austin trammell", "tim jones", "dylan drummond",
      "xavier gipson", "dominic lovett", "michael bandy",
      "xavier restrepo"
    ]);
    const isFlagged = ({ player }) =>
      flaggedIds.has(String(player.id)) ||
      flaggedNames.has(normalizeName(player.name));
    const eligible = rankings.filter(entry => !isFlagged(entry));
    const flagged = rankings.filter(isFlagged);
    if (flagged.length) {
      rankings.splice(0, rankings.length, ...eligible, ...flagged);
      console.info("Week 8 WR editorial role safeguard:",
        flagged.map(entry => entry.player.name).join(", "));
    }
  }

  // Week 7 editorial RB placement: Wilson's recent lead-back workload
  // predates returning-back competition. Place him beside Dameon Pierce
  // without altering the underlying AI Score or other positions.
  if (position === "RB" &&
      Number(document.documentElement.dataset.targetWeek) === 7) {
    const wilsonIndex = rankings.findIndex((entry) =>
      String(entry.player.id) === "11435" &&
      entry.player.team === "SEA"
    );
    const pierceIndex = rankings.findIndex((entry) =>
      normalizeName(entry.player.name) === normalizeName("Dameon Pierce")
    );
    if (wilsonIndex >= 0 && pierceIndex >= 0) {
      const [wilson] = rankings.splice(wilsonIndex, 1);
      const newPierceIndex = rankings.findIndex((entry) =>
        normalizeName(entry.player.name) === normalizeName("Dameon Pierce")
      );
      rankings.splice(newPierceIndex + 1, 0, wilson);
      console.info("Week 7 RB editorial placement: Emanuel Wilson after Dameon Pierce; model score unchanged.");
    }
  }

  rankingCache[cacheKey] = rankings;
 
  return rankings;
}

function getPlayerPositionRank(player, profile) {
  if (!player || !player.position) {
    return null;
  }

  const rankings =
    getPositionRankings(player.position, profile);

  const index = rankings.findIndex(
    (entry) => entry.player.id === player.id
  );

  return index >= 0 ? index + 1 : null;
}

function getRecommendation(player, positionRank) {
  if (!player) {
    return "SIT";
  }

  const playerTeam =
    player.team === "LA"
      ? "LAR"
      : player.team;

  const weeklyMatchup =
    teamNextOpponent[playerTeam];

 
  // Only identify a bye when the matchup data
  // matches the displayed NFL week.
  const matchupWeekAligned =
    document.documentElement.dataset
      .matchupWeekAligned !== "false";

  if (
    matchupWeekAligned &&
    String(weeklyMatchup?.opponent || "")
      .trim()
      .toUpperCase() === "BYE"
  ) {
    return "BYE";
  }


  const injury = String(player.injuryStatus || "")

    .trim()
    .toUpperCase();

  const rosterStatus = String(player.status || "")
    .trim()
    .toUpperCase();

  if (
    injury === "OUT" ||
    rosterStatus === "INACTIVE" ||
    rosterStatus === "INJURED_RESERVE" ||
    rosterStatus === "SUSPENDED"
  ) {
    return "OUT";
  }

  if (!positionRank) {
    return "SIT";
  }

  if (player.position === "QB") {
    return positionRank <= 12
      ? "START"
      : "SIT";
  }

  if (player.position === "RB") {
    if (positionRank <= 24) {
      return "START";
    }

    if (positionRank <= 36) {
      return "FLEX";
    }

    return "SIT";
  }

  if (player.position === "WR") {
    if (positionRank <= 24) {
      return "START";
    }

    if (positionRank <= 36) {
      return "FLEX";
    }

    return "SIT";
  }

  if (player.position === "TE") {
    return positionRank <= 12
      ? "START"
      : "SIT";
  }

  return "SIT";
}
function getTopSignals(player) {
  const metrics = getMetrics(player);

 const positiveSignals = [
  ["Recent Production", metrics.production],
  ["Opportunity", metrics.opportunity],
  ["Usage", metrics.usage],
  ["Red-Zone Usage", metrics.redzone],
  ["Matchup", metrics.matchup],
  ["Scoring Environment", metrics.scoringEnvironment],
  ["Play Caller Matchup", metrics.playCallerMatchup],
  [
    "Player vs Defensive Play Caller",
    metrics.playerVsDefensiveCaller
  ],
  ["Model Confidence", metrics.expert],
  ["Risk Adjustment", 100 - metrics.risk]
];

  return positiveSignals
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
}

let currentSignalPlayer = null;
function metricRow(
  label,
  value,
  isRisk = false,
  breakdown = null,
  signalDetails = null,
  evidence = ""
) {
  const info =
    metricDescriptions[label];

  const description = info
    ? info.description
    : "";

  const weight = info
    ? info.weight
    : "";

  const extraEvidence = ["Matchup", "Play Caller Matchup", "Player vs Defensive Play Caller",
    "Red-Zone Usage", "Scoring Environment", "Model Confidence", "Risk Adjustment"].includes(label)
    ? getAdditionalSignalEvidence(currentSignalPlayer, label, signalDetails, breakdown)
    : "";
  const breakdownHtml =
    false && label === "Model Confidence" &&
    breakdown
      ? `
        <div class="confidence-breakdown">
          <strong>Confidence breakdown</strong>

          <div>
            Production Consistency
            <span>
              ${breakdown.productionConsistency}/100
              · 35%
            </span>
          </div>

          <div>
            Opportunity Stability
            <span>
              ${breakdown.opportunityStability}/100
              · 30%
            </span>
          </div>

          <div>
            Usage Stability
            <span>
              ${breakdown.usageStability}/100
              · 20%
            </span>
          </div>

          <div>
            Availability
            <span>
              ${breakdown.availability}/100
              · 15%
            </span>
          </div>
        </div>
      `
      : "";
const signalDetailsHtml =
  false && signalDetails
    ? `
      <div class="confidence-breakdown">

        ${
          signalDetails.offensivePlayCaller
            ? `
              <div>
                Offensive Play Caller
                <span>
                  ${signalDetails.offensivePlayCaller}
                </span>
              </div>
            `
            : ""
        }

        <div>
          Defensive Play Caller
          <span>
            ${signalDetails.defensivePlayCaller}
          </span>
        </div>

        <div>
          Upcoming Opponent
          <span>
            ${signalDetails.opponent}
          </span>
        </div>

        <div>
          Historical PPR Average
          <span>
            ${
              signalDetails.averagePpr !== null &&
              signalDetails.averagePpr !== undefined
                ? Number(
                    signalDetails.averagePpr
                  ).toFixed(1)
                : "No history"
            }
          </span>
        </div>

        <div>
          Historical Sample
          <span>
            ${
              signalDetails.sampleSize === 1
                ? "1 game"
                : `${signalDetails.sampleSize} games`
            }
          </span>
        </div>

      </div>
    `
    : "";
  return `
    <div class="metric-row">
      <div class="metric-label-row">

        <span class="metric-name">
          ${label}

          <button
            type="button"
            class="metric-info-button"
            aria-label="Explain ${label}"
            onclick="
              this.closest('.metric-row')
                .querySelector('.metric-explanation')
                .classList.toggle('active')
            "
          >
            i
          </button>
        </span>

        <strong>${value}/100</strong>
      </div>

      <div class="metric-track">
        <div
          class="metric-fill"
          style="width:${value}%"
        ></div>
      </div>

      <div class="metric-explanation">
        <div class="metric-explanation-heading">
          <strong>${label}</strong>
      <span>
        ${weight} of Balanced score
      </span>
    </div>

        <p>${description}</p>

        ${evidence
          ? ["Opportunity", "Recent Production", "Usage"].includes(label)
            ? evidence
            : `<div class="metric-sample-size">${evidence}</div>`
          : ""}

        ${breakdownHtml}
        
        ${extraEvidence}
      </div>
    </div>
  `;
}

function renderPlayerCard(
  player,
  score,
  recommendation,
  positionRank
) {
  currentSignalPlayer = player;
  const metrics = getMetrics(player);
  const topSignals = getTopSignals(player);
  const riskAdjustment = 100 - metrics.risk;
  const confidenceBreakdown =
  getModelConfidenceBreakdown(player);
  const playCallerDetails =
  getPlayCallerMatchupDetails(player);
 
  const playerVsCallerDetails =
  getPlayerVsDefensiveCallerDetails(player);
  const trench = getTrenchMatchup(player);
  const gameCompleted = isPlayerMatchupCompleted(player);

  const projection =
    getPlayerPprProjection(player);

  const projectedPpr =
    projection &&
    Number.isFinite(
      projection.projected_ppr
    )
      ? projection.projected_ppr.toFixed(2)
      : "—";

  const projectedRank =
    projection &&
    Number.isFinite(
      projection.projected_position_rank
    )
      ? `${player.position}${projection.projected_position_rank}`
      : "—";
  
  const injuryBoost = snapshotWeek
    ? 0
    : calculateInjuryOpportunityBoost(player);
  const isPriorOnlyRookie =
    player.nflId &&
    fantasyAiScores[player.nflId]?.available === true &&
    fantasyAiScores[player.nflId]
      ?.rookie_prior_adjustment?.prior_only === true;  
  return `

    <article class="player-result-card">
      <div class="player-comparison-header">
      <div class="player-result-top">
        <div>
          <h3 class="player-name">${player.name}</h3>
 <p class="player-meta">
  ${player.position} • ${player.team}
  ${
    positionRank
      ? ` • ${player.position}${positionRank}`
      : ""
  }
</p>

<div class="player-status">
  <span>
    Injury:
    <strong>
      ${player.injuryStatus || "None"}
    </strong>
  </span>

  <span>
    Practice:
    <strong>
      ${player.practiceParticipation || "No designation"}
    </strong>
  </span>

  ${
    player.depthChartOrder
      ? `
        <span>
          Depth chart:
          <strong>#${player.depthChartOrder}</strong>
        </span>
      `
      : ""
  }
</div>
        </div>

       
        <div class="recommendation-badge">
          ${recommendation === "BYE" ? "BYE WEEK" : recommendation}
        </div>
      </div>

      ${recommendation === "BYE" ? `
        <div class="player-bye-notice" role="status">
          <strong>BYE WEEK</strong>
          <p>
            This player has no scheduled game this week.
            Do not start them in your fantasy lineup.
            Their AI Score reflects model signals,
            not projected points for this bye week.
          </p>
        </div>
      ` : ""}

      <div class="player-score-summary">

        <div class="player-score-block">
          <span class="player-score-label">
            AI SCORE
          </span>

          <div class="player-score">
            ${score}<span>/100</span>
          </div>

          <span class="player-score-rank">
            ${positionRank
              ? `${player.position}${positionRank}`
              : "—"}
          </span>
        </div>

        <div class="player-score-block">
          <span class="player-score-label">
            PROJECTED PPR
          </span>

          <div class="player-projected-ppr">
            ${recommendation === "BYE" ? "BYE" : projectedPpr}
          </div>

          <span class="player-score-rank">
            ${recommendation === "BYE" ? "No game scheduled" : projectedRank}
          </span>

        </div>
      </div>


      <div class="why-section">
  <h4>Why this player?</h4>

  ${
    player.nflId &&
    fantasyAiScores[player.nflId]?.available &&
    fantasyAiScores[player.nflId]
      ?.rookie_prior_adjustment?.prior_only
      ? `
        <p>
          <strong>Rookie draft-capital projection</strong>
        </p>
        <p>
          Based on historical performance of rookies
          drafted in similar positions.
        </p>
        <p>
          No recorded NFL statistical games yet.
          This is a projection, not demonstrated
          NFL production.
        </p>
      `
      : `
        <ul>
          ${topSignals.map(([label, value]) => `
            <li>
              <strong>${label}</strong> ${value}/100
            </li>
          `).join("")}
        </ul>
      `
  }
</div>
      </div>

      <div class="metrics-section">
  ${
    isPriorOnlyRookie
      ? `
        <div class="metric-row">
          <div class="metric-label-row">
            <span class="metric-name">
              Draft-Capital Projection
            </span>
            <strong>
              ${fantasyAiScores[player.nflId].score.toFixed(1)}/100
            </strong>
          </div>
          <div class="metric-track">
            <div
              class="metric-fill"
              style="width:${fantasyAiScores[player.nflId].score}%"
            ></div>
          </div>
          <p>
            Historical rookie projection.
            No NFL statistical games recorded.
          </p>
        </div>
      `
      : `

        ${metricRow(
          "Opportunity",
          metrics.opportunity,
          false,
          null,
          null,
          getCoreSignalEvidence(player, "Opportunity")
        )}

        ${metricRow(
          "Recent Production",
          metrics.production,
          false,
          null,
          null,
          getCoreSignalEvidence(player, "Recent Production")
        )}

        ${metricRow(
          "Usage",
          metrics.usage,
          false,
          null,
          null,
          getCoreSignalEvidence(player, "Usage")
        )}

        ${metricRow(
          "Matchup",
          metrics.matchup,
          false,
          null,
          null,
          "Opponent defensive data · positional fantasy points allowed · historical game count not provided by this signal"
        )}

        ${metricRow(
          "Play Caller Matchup",
          metrics.playCallerMatchup,
          false,
          null,
          playCallerDetails,
          null
        )}

        ${metricRow(
          "Player vs Defensive Play Caller",
          metrics.playerVsDefensiveCaller,
          false,
          null,
          playerVsCallerDetails,
          null
        )}

        ${metricRow(
          "Red-Zone Usage",
          metrics.redzone,
          false,
          null,
          null,
          player.position === "QB"
            ? getRedZoneEvidence(player)
            : getWeightedRedZoneEvidence(player)        )}

        ${metricRow(
          "Scoring Environment",
          metrics.scoringEnvironment,
          false,
          null,
          null,
          null
        )}

        ${metricRow(
          "Model Confidence",
          metrics.expert,
          false,
          confidenceBreakdown,
          null,
          getConfidenceEvidence(player)
        )}

        ${metricRow(
          "Risk Adjustment",
          riskAdjustment,
          true,
          null,
          null,
          getRiskEvidence(player)
        )}


        <div class="metric-row trench-signal">
          <div class="metric-label-row">
            <span class="metric-name">
              Trench Matchup

              <button
                type="button"
                class="metric-info-button"
                aria-label="Explain Trench Matchup"
                onclick="
                  this.closest('.metric-row')
                    .querySelector('.metric-explanation')
                    .classList.toggle('active')
                "
              >
                i
              </button>
            </span>

            <strong>
              ${trench
                ? trench.score.toFixed(1) + "/100"
                : gameCompleted
                  ? "Game completed"
                  : "Data unavailable"}
            </strong>
          </div>

          ${trench
            ? `<div class="metric-track">
                 <div class="metric-fill"
                   style="width:${trench.score}%">
                 </div>
               </div>`
            : ""}

          <div class="metric-explanation">
            <div class="metric-explanation-heading">
              <strong>Trench Matchup</strong>
              <span>7% of Balanced score when available</span>
            </div>

            <p>
              ${trench
                ? `Measures the offensive line matchup against the ${trench.opponent} defensive front.
                   ${trench.injuryAdjusted
                     ? "Pregame offensive-line availability is included in the matchup."
                     : "This is currently a team-level matchup; offensive-line injury adjustment is unavailable."}`
                : gameCompleted
                  ? "This matchup has recorded game statistics, so the pregame trench signal is no longer applicable."
                  
                  : "No verified pregame trench matchup data is available for this opponent."}
            </p>

            ${getAdditionalSignalEvidence(player, "Trench Matchup", null, null, trench)}

          </div>

        </div>
        `}

      ${injuryBoost > 0 && !["OUT", "IR", "PUP"].includes(
        String(player.injuryStatus || "").toUpperCase()
      ) ? `

<div class="injury-opportunity-boost">
  <strong>Injury Opportunity Boost</strong>
  <span>+${injuryBoost} model points</span>

  ${(injuryOpportunityDetailsCache.get(player.id) || [])
    .map((detail) => `
      <div class="injury-boost-detail">
        <strong>${detail.name}</strong>
        <span>
          ${detail.status}
          ${detail.provisional ? " · Provisional" : ""}
          · +${detail.points} points
        </span>
      </div>
    `).join("")}

  <p>
    Experimental adjustment based on teammate
    availability and recent usage.
  </p>
</div>

      ` : ""}

      </article>
  `;
} 

function comparePlayers() {
  
  const playerA = getPlayer(playerASelect.value);
  const playerB = getPlayer(playerBSelect.value);
  const playerC = getPlayer(playerCSelect.value);

  if (!playerA || !playerB || !playerC) return;



  const profile = riskSelect.value;

  const scoreA = calculateScore(playerA, profile);
  const scoreB = calculateScore(playerB, profile);
  const scoreC = calculateScore(playerC, profile);

  const positionRankA = getPlayerPositionRank(playerA, profile);
  const positionRankB = getPlayerPositionRank(playerB, profile);
  const positionRankC = getPlayerPositionRank(playerC, profile);

  const recommendationA = getRecommendation(playerA, positionRankA);
  const recommendationB = getRecommendation(playerB, positionRankB);
  const recommendationC = getRecommendation(playerC, positionRankC);

  const profileName =
    profile.charAt(0).toUpperCase() + profile.slice(1);

  resultsContainer.innerHTML = `
  <section class="comparison-results">
    <div class="comparison-heading">
      <p class="eyebrow">PLAYER COMPARISON</p>
      
      <h2>3-Player Comparison</h2>
      <p>${playerA.name} vs. ${playerB.name} vs. ${playerC.name}</p>
      <p>${profileName} risk profile</p>
    </div>

    
    <div class="player-results-grid">
      ${renderPlayerCard(
        playerA,
        scoreA,
        recommendationA,
        positionRankA
      )}

      ${renderPlayerCard(
        playerB,
        scoreB,
        recommendationB,
        positionRankB
      )}

      ${renderPlayerCard(
        playerC,
        scoreC,
        recommendationC,
        positionRankC
      )}
    </div>

    
    <div class="verdict-card">
      <p class="eyebrow">THREE-PLAYER COMPARISON</p>

      <h3>
        ${
          (() => {
            const topScore = Math.max(scoreA, scoreB, scoreC);
            const leaders = [
              [playerA, scoreA],
              [playerB, scoreB],
              [playerC, scoreC]
            ].filter(([, score]) => score === topScore);

            return leaders.length === 1
              ? `${leaders[0][0].name} has the highest model score`
              : `${leaders.map(([player]) => player.name).join(" and ")} are tied`;
          })()
        }
      </h3>

      <p>
        Scores reflect the current ${profileName.toLowerCase()}
        risk profile, including Trench Matchup and Scoring Environment when available.
      </p>

      <div class="verdict-scores">
        <div>
          <span>${playerA.name}</span>
          <strong>${scoreA}</strong>
        </div>

        <div>
          <span>${playerB.name}</span>
          <strong>${scoreB}</strong>
        </div>

        <div>
          <span>${playerC.name}</span>
          <strong>${scoreC}</strong>
        </div>
      </div>
    </div>

    <div class="model-note">
  <strong>Model note:</strong>
  This MVP combines historical NFL performance, usage, red-zone involvement,
  upcoming matchup context, player availability, and model-derived confidence.
  Play-caller matchup history adds coaching-context signals to the comparison model.
  Expert consensus remains a planned future data-source enhancement.
</div>
  </section>
`;
}
function exportModelSnapshot() {
  const profile = "balanced";
  const positions = ["QB", "RB", "WR", "TE"];

  const snapshot = [];

  positions.forEach((position) => {
    const rankings =
      getPositionRankings(position, profile);

    rankings.forEach((entry, index) => {
      const player = entry.player;
      const positionRank = index + 1;

      const recommendation =
        getRecommendation(
          player,
          positionRank
        );

      const playCallerDetails =
        getPlayCallerMatchupDetails(player);

      const playerVsCallerDetails =
        getPlayerVsDefensiveCallerDetails(player);

      const metrics =
        getMetrics(player);

      const trench =
        getTrenchMatchup(player);

      snapshot.push({
        snapshot_week:
          Number(
            document.documentElement.dataset.targetWeek
          ) || null,
        player_id:
          player.nflId || player.id,
        player_name: player.name,
        position: player.position,
        team: player.team === "LAR" ? "LA" : player.team,
        roster_status: player.status || "UNKNOWN",
        injury_status: player.injuryStatus || "",

        opponent:
          playCallerDetails?.opponent ||
          playerVsCallerDetails?.opponent ||
          "Unknown",

        offensive_play_caller:
          playCallerDetails?.offensivePlayCaller ||
          "Unknown",

        defensive_play_caller:
          playCallerDetails?.defensivePlayCaller ||
          playerVsCallerDetails?.defensivePlayCaller ||
          "Unknown",

        play_caller_matchup_score:
          metrics.playCallerMatchup,

        play_caller_historical_ppr:
          playCallerDetails?.averagePpr ?? "",

        play_caller_sample_size:
          playCallerDetails?.sampleSize ?? 0,

        player_vs_defensive_caller_score:
          metrics.playerVsDefensiveCaller,

        player_vs_defensive_caller_ppr:
          playerVsCallerDetails?.averagePpr ?? "",

        player_vs_defensive_caller_sample_size:
          playerVsCallerDetails?.sampleSize ?? 0,

        opportunity_score: metrics.opportunity,
        production_score: metrics.production,
        usage_score: metrics.usage,
        matchup_score: metrics.matchup,
        redzone_score: metrics.redzone,
        expert_score: metrics.expert,
        risk_score: metrics.risk,
        trench_score: trench ? trench.score : null,

        scoring_environment_score:
          getScoringEnvironment(player)?.score ?? null,

        implied_team_total:
          getScoringEnvironment(player)?.impliedTeamTotal ?? null,

        game_total:
          getScoringEnvironment(player)?.gameTotal ?? null,

        spread_line:
          getScoringEnvironment(player)?.spread ?? null,

        model_score: entry.score,
        position_rank: positionRank,
        recommendation: recommendation
      });
    });
  });

  const header = [
    "snapshot_week",
    "player_id",
    "player_name",
    "position",
    "team",
    "roster_status",
    "injury_status",
    "opponent",
    "offensive_play_caller",
    "defensive_play_caller",
    "play_caller_matchup_score",
    "play_caller_historical_ppr",
    "play_caller_sample_size",
    "player_vs_defensive_caller_score",
    "player_vs_defensive_caller_ppr",
    "player_vs_defensive_caller_sample_size",
    "opportunity_score",
    "production_score",
    "usage_score",
    "matchup_score",
    "redzone_score",
    "expert_score",
    "risk_score",
    "trench_score",
    "scoring_environment_score",
    "implied_team_total",
    "game_total",
    "spread_line",
    "model_score",
    "position_rank",
    "recommendation"
  ];

  const escapeCsv = (value) =>
    `"${String(value ?? "").replace(/"/g, '""')}"`;

  const rows = snapshot.map((player) =>
    [
      player.snapshot_week,
      player.player_id,
      escapeCsv(player.player_name),
      player.position,
      player.team,
      escapeCsv(player.roster_status),
      escapeCsv(player.injury_status),
      player.opponent,
      escapeCsv(player.offensive_play_caller),
      escapeCsv(player.defensive_play_caller),
      player.play_caller_matchup_score,
      player.play_caller_historical_ppr,
      player.play_caller_sample_size,
      player.player_vs_defensive_caller_score,
      player.player_vs_defensive_caller_ppr,
      player.player_vs_defensive_caller_sample_size,
      player.opportunity_score,
      player.production_score,
      player.usage_score,
      player.matchup_score,
      player.redzone_score,
      player.expert_score,
      player.risk_score,
      player.trench_score,
      player.scoring_environment_score,
      player.implied_team_total,
      player.game_total,
      player.spread_line,
      player.model_score,
      player.position_rank,
      player.recommendation
    ].join(",")
  );

  const csv = [
    header.join(","),
    ...rows
  ].join("\n");

  const blob = new Blob(
    [csv],
    { type: "text/csv;charset=utf-8;" }
  );

  const url =
    URL.createObjectURL(blob);

  const link =
    document.createElement("a");

  link.href = url;

  const exportWeek = snapshotWeek || "live";

  link.download =
    snapshotWeek
      ? `2026-week${exportWeek}-model-snapshot.csv`
      : "2026-live-model-snapshot.csv";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);

  console.log(
    snapshotWeek
      ? `Week ${snapshotWeek} model snapshot exported: ${snapshot.length} players`
      : `Live model snapshot exported: ${snapshot.length} players`
  );
}
function getActualPprForRanking(player) {
  const week = Number(snapshotWeek || document.documentElement.dataset.targetWeek);
  if (!Number.isInteger(week) || week < 1 || !player) return null;

  const team = value => ({LA: "LAR", JAC: "JAX", WSH: "WAS"})[
    String(value || "").toUpperCase()
  ] || String(value || "").toUpperCase();
  const name = normalizeName(player.name);
  const position = String(player.position || "").toUpperCase();

  // Use published completed-game results, not the pregame projection dataset.
  // Require a unique identity match; never assign another player's points.
  const results = actualPprResults.filter(game =>
    Number(game.season) === 2026 &&
    Number(game.week) === week &&
    normalizeName(game.player_display_name) === name &&
    String(game.position || "").toUpperCase() === position &&
    team(game.team) === team(player.team)
  );
  const games = results.length ? results : getPlayerWeeklyStats(player).filter(game =>
    Number(game.season) === 2026 && Number(game.week) === week
  );
  if (games.length !== 1) return null;
  const game = games[0];
  const raw = [game.fantasy_points_ppr, game.ppr_points, game.ppr]
    .find(value => value !== null && value !== undefined && value !== "");
  if (raw === undefined) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

const RANKINGS_PER_PAGE = 24;
let currentRankingPage = 1;

function renderPositionRankings() {
  const positionSelect =
    document.getElementById("rankingPosition");

  const searchInput =
    document.getElementById("rankingSearch");

  const tableBody =
    document.getElementById("rankingTableBody");

  const weekLabel =
    document.getElementById("rankingWeek");

  const pagination =
    document.getElementById("rankingPagination");

  if (!positionSelect || !tableBody) return;

  const position = positionSelect.value;
  const profile = riskSelect.value;

  const query =
    (searchInput?.value || "")
      .trim()
      .toLowerCase();

  if (weekLabel) {
    weekLabel.textContent = snapshotWeek
      ? `2026 Week ${snapshotWeek} rankings`
      : "Live positional rankings";
  }

  delete rankingCache[
    `${profile}-${position}`
  ];

      const rankings =
    getPositionRankings(position, profile)
      .filter(({ player }) =>
        player.name
          .toLowerCase()
          .includes(query)
      );
  tableBody.innerHTML = "";

  if (rankings.length === 0) {
    tableBody.innerHTML =
      '<tr><td colspan="8">No ranked players found.</td></tr>';

    if (pagination) {
      pagination.innerHTML = "";
    }

    return;
  }

  const totalPages =
    Math.ceil(
      rankings.length /
      RANKINGS_PER_PAGE
    );

  if (currentRankingPage > totalPages) {
    currentRankingPage = totalPages;
  }

  if (currentRankingPage < 1) {
    currentRankingPage = 1;
  }

  const startIndex =
    (currentRankingPage - 1) *
    RANKINGS_PER_PAGE;

  const endIndex =
    startIndex + RANKINGS_PER_PAGE;

  const visibleRankings =
    rankings.slice(
      startIndex,
      endIndex
    );

  visibleRankings.forEach(
    ({ player, score }) => {

      const rank =
        getPlayerPositionRank(
          player,
          profile
        );

      const matchup =
        teamNextOpponent[player.team];

      const projection =
        getPlayerPprProjection(player);

      const opponent =
        projection?.opponent || matchup?.opponent || "TBD";

      const projectedPpr =
        projection &&
        Number.isFinite(
          projection.projected_ppr
        )
          ? projection.projected_ppr.toFixed(2)
          : "—";

      const projectedRank =
        projection &&
        Number.isFinite(
          projection.projected_position_rank
        )
          ? `${player.position}${projection.projected_position_rank}`
          : "—";

      const actualPpr = getActualPprForRanking(player);
      const row =
        document.createElement("tr");
      
      [
        `${player.position}${rank}`,
        player.name,
        score.toFixed(1),
        opponent,
        projectedPpr,
        projectedRank,
        actualPpr === null ? "—" : actualPpr.toFixed(2),
        player.injuryStatus ||
          "Available"
      ].forEach((value) => {


        const cell =
          document.createElement("td");

        cell.textContent = value;

        row.appendChild(cell);
      });

      tableBody.appendChild(row);
    }
  );

  if (!pagination) return;

  pagination.innerHTML = "";

  if (totalPages <= 1) {
    return;
  }

  const previousButton =
    document.createElement("button");

  previousButton.type = "button";
  previousButton.textContent = "← Previous";

  previousButton.disabled =
    currentRankingPage === 1;

  previousButton.addEventListener(
    "click",
    () => {
      if (currentRankingPage <= 1) {
        return;
      }

      currentRankingPage -= 1;
      renderPositionRankings();

      document
        .getElementById("rankings")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
    }
  );

  pagination.appendChild(
    previousButton
  );


  const pageStatus =
    document.createElement("span");

  pageStatus.className =
    "ranking-page-status";

  pageStatus.textContent =
    `Page ${currentRankingPage} of ${totalPages}`;

  pagination.appendChild(
    pageStatus
  );


  const nextButton =
    document.createElement("button");

  nextButton.type = "button";
  nextButton.textContent = "Next →";

  nextButton.disabled =
    currentRankingPage === totalPages;

  nextButton.addEventListener(
    "click",
    () => {
      if (
        currentRankingPage >=
        totalPages
      ) {
        return;
      }

      currentRankingPage += 1;
      renderPositionRankings();

      document
        .getElementById("rankings")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
    }
  );

  pagination.appendChild(
    nextButton
  );
}
compareButton.addEventListener("click", comparePlayers);

async function initializeApp() {

  // Load weekly NFL data first so the current
  // target week is known.
  await loadWeeklyStats();
  await loadVerifiedInjuryOuts();
  await loadTrenchRateDetails();

  // Load Model F PPR projections for that week.
  await loadWeeklyPprProjections();

 
  // Load the current NFL player pool and connect
  // Sleeper players to NFL/GSIS IDs.
  await loadPlayers();

  // Load the latest game-day availability snapshot.
  // A missing or stale snapshot will not block startup.
  
  await loadGamedayAvailability();
  await loadLineupKickoffSchedule();
  await loadNflInactiveObservations();



  console.log(
    "PPR projection mapping check:",
    {
      projections:
        weeklyPprProjections.length,

      matchedPlayers:
        players.filter(
          player =>
            getPlayerPprProjection(player)
        ).length,

      bryceYoung:
        getPlayerPprProjection(
          players.find(
            player =>
              player.name ===
              "Bryce Young"
          )
        ),

      jahmyrGibbs:
        getPlayerPprProjection(
          players.find(
            player =>
              player.name ===
              "Jahmyr Gibbs"
          )
        )
    }
  );

  // Display rankings and projections after
  // all data sources load.
  renderPositionRankings();
  renderProjectionBoard();
  renderWeeklySleepers();
  await loadWaiverWire();
  // Add the snapshot export button.
  const rankingSelect =
    document.getElementById("rankingPosition");

  if (rankingSelect) {
    const exportButton =
      document.createElement("button");

    exportButton.type = "button";
    exportButton.id = "exportSnapshotBtn";
    exportButton.textContent = "Export Snapshot";
    exportButton.style.display = "block";
    exportButton.style.width = "180px";
    exportButton.style.maxWidth = "100%";
    exportButton.style.margin = "12px 0 16px auto";
    exportButton.style.padding = "10px 14px";
    exportButton.style.backgroundColor = "#f7c651";
    exportButton.style.color = "#17212f";
    exportButton.style.border = "none";
    exportButton.style.borderRadius = "8px";
    exportButton.style.fontWeight = "700";
    exportButton.style.fontSize = "13px";
    exportButton.style.cursor = "pointer";

    exportButton.addEventListener(
      "click",
      exportModelSnapshot
    );

    rankingSelect.insertAdjacentElement(
      "afterend",
      exportButton
    );
  }
  // Update rankings when the selected position changes.
 document
  .getElementById("rankingPosition")
  ?.addEventListener(
    "change",
    () => {
      currentRankingPage = 1;
      renderPositionRankings();
    }
  );

  // Filter rankings as the user searches.
  document
    .getElementById("rankingSearch")
    ?.addEventListener(
      "input",
      () => {
        currentRankingPage = 1;
        renderPositionRankings();
      }
    );

  const projectionSearch =
    document.getElementById(
      "projectionSearch"
    );

  if (projectionSearch) {
    projectionSearch.addEventListener(
      "input",
      () => {
        currentProjectionPage = 1;
        renderProjectionBoard();
      }
    );
  }

  document
    .querySelectorAll(
      "[data-projection-position]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        () => {
          currentProjectionPosition =
            button.dataset
              .projectionPosition ||
            "ALL";

          currentProjectionPage = 1;

          document
            .querySelectorAll(
              "[data-projection-position]"
            )
            .forEach(
              filterButton => {
                filterButton
                  .classList
                  .toggle(
                    "active",
                    filterButton ===
                      button
                  );
              }
            );

          renderProjectionBoard();
        }
      );
    });
  document
    .querySelectorAll(
      "[data-sleeper-position]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        () => {
          currentSleeperPosition =
            button.dataset
              .sleeperPosition ||
            "ALL";

          document
            .querySelectorAll(
              "[data-sleeper-position]"
            )
            .forEach(
              filterButton => {
                filterButton
                  .classList
                  .toggle(
                    "active",
                    filterButton ===
                      button
                  );
              }
            );

          renderWeeklySleepers();
        }
      );
    });
  const manualRosterTab =
    document.getElementById(
      "manualRosterTab"
    );

  const screenshotRosterTab =
    document.getElementById(
      "screenshotRosterTab"
    );

  const lineupScreenshotInput =
    document.getElementById(
      "lineupScreenshotInput"
    );

  const lineupScreenshotSelectBtn =
    document.getElementById(
      "lineupScreenshotSelectBtn"
    );


  if (manualRosterTab) {
    manualRosterTab.addEventListener(
      "click",
      () => {
        setLineupRosterMethod(
          "manual"
        );
      }
    );
  }


  if (screenshotRosterTab) {
    screenshotRosterTab.addEventListener(
      "click",
      () => {
        setLineupRosterMethod(
          "screenshot"
        );
      }
    );
  }


  if (
    lineupScreenshotSelectBtn &&
    lineupScreenshotInput
  ) {
    lineupScreenshotSelectBtn
      .addEventListener(
        "click",
        () => {
          lineupScreenshotInput.click();
        }
      );
  }


  if (lineupScreenshotInput) {
    lineupScreenshotInput.addEventListener(
      "change",
      handleLineupScreenshotSelection
    );
  }


  setLineupRosterMethod("manual");

  const lineupPlayerSearch =
    document.getElementById(
      "lineupPlayerSearch"
    );


  if (lineupPlayerSearch) {
    lineupPlayerSearch.addEventListener(
      "input",
      renderLineupPlayerResults
    );
  }


  const clearLineupButton =
    document.getElementById(
      "clearLineupRoster"
    );

  if (clearLineupButton) {
    clearLineupButton.addEventListener(
      "click",
      clearLineupRoster
    );
  }


  const lineupFormat =
    document.getElementById(
      "lineupFormat"
    );

  if (lineupFormat) {
    lineupFormat.addEventListener(
      "change",
      updateLineupFormatControls
    );
  }
  const optimizeLineupButton =
    document.getElementById(
      "optimizeLineupBtn"
    );

  if (optimizeLineupButton) {
    optimizeLineupButton.addEventListener(
      "click",
      optimizeLineup
    );
  }
  updateLineupFormatControls();
  renderLineupRoster();
  
  // Refresh rankings when risk tolerance changes.
  riskSelect.addEventListener("change", () => {
    renderPositionRankings();
    renderProjectionBoard();
  });

  // Refresh injury designations every five minutes.
  setInterval(refreshPlayerInjuries, 5 * 60 * 1000);
}

initializeApp();

