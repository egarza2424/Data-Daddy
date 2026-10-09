
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
      "Measures involvement inside the opponent's 20-yard line. QB uses red-zone pass attempts + carries. RB/WR/TE use their share of team red-zone carries + targets."
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

async function loadWeeklyStats() {
  try {
const response = await fetch(
  `${statsFile}?v=13`,
  { cache: "no-store" }
);
    if (!response.ok) {
      throw new Error(
        `Could not load ${statsFile}: ${response.status}`
      );
    }

    const data = await response.json();

weeklyStats = data.players || [];
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

document.documentElement.dataset.targetWeek =
  data.target_week || "";

currentPlayerVsDefensiveCaller =
  data.current_player_vs_defensive_caller || {};
  
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
        });

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
        return [
          player.nflId,
          player.id
        ]
          .filter(Boolean)
          .map(id => String(id))
          .includes(projectionId);
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

  return (
    players.find((player) => {
      return (
        normalizeName(player.name) ===
          projectionName &&
        String(
          player.position || ""
        ).toUpperCase() ===
          projectionPosition
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
        if (rankAdvantage <= 0) {
          return null;
        }

        return {
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
            candidate.rankAdvantage
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
              candidate.rankAdvantage,
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
  const sleepers =
    filteredSleepers.slice(0, 10);

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

      const matchup =
        teamNextOpponent[
          player.team
        ];

      const opponent =
        matchup?.opponent ||
        projection.opponent ||
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
            #${index + 1}
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

    if (provisional.length > 0) {
      container.replaceChildren();

      const notice = document.createElement("p");
      notice.textContent =
        `Week ${data.target_week} — Provisional Top 10. ` +
        "These are model-ranked candidates, not final pickup recommendations. " +
        "Official injury availability, player roles, and matchups remain under review.";
      container.appendChild(notice);

      provisional.forEach((player) => {
        const row = document.createElement("div");
        row.className = "waiver-player";

        const title = document.createElement("strong");
        title.textContent =
          `#${player.provisional_rank} ${player.name} ` +
          `(${player.position} • ${player.team})`;

        const details = document.createElement("p");
        const ownership = Number(player.average_rostered);
        const score = Number(player.waiver_evidence_score);

        details.textContent =
          `Rostered: ${Number.isFinite(ownership) ? ownership.toFixed(1) + "%" : "Unverified"} ` +
          `• Evidence score: ${Number.isFinite(score) ? score.toFixed(1) : "—"} ` +
          `• Injury verification pending`;

        row.append(title, details);
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

  if (!tableBody) {
    return;
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
        <td colspan="9">
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

      const aiScore =
        Number(
          projection.model_score
        );

      const aiRank =
        player
          ? getPlayerPositionRank(
              player
            )
          : null;

      const matchup =
        player
          ? teamNextOpponent[
              player.team
            ]
          : null;

      const opponent =
        matchup?.opponent ||
        projection.opponent ||
        "TBD";

      const status =
        player?.injuryStatus ||
        "Available";

      const row =
        document.createElement("tr");

      const values = [
        Number.isFinite(
          projectedRank
        )
          ? `${position}${projectedRank}`
          : "—",

        projection.player_name ||
          "Unknown",

        position || "—",

        projection.team || "—",

        opponent,

        Number.isFinite(aiScore)
          ? aiScore.toFixed(1)
          : "—",

        aiRank
          ? `${position}${aiRank}`
          : "—",

        Number.isFinite(
          projectedPpr
        )
          ? projectedPpr.toFixed(2)
          : "—",

        status
      ];

      values.forEach(
        (value, index) => {
          const cell =
            document.createElement("td");

          cell.textContent =
            String(value);

          if (index === 7) {
            cell.classList.add(
              "projection-ppr-value"
            );
          }

          row.appendChild(cell);
        }
      );

      tableBody.appendChild(row);
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


function getLineupPlayersByPosition() {
  const groups = {
    QB: [],
    RB: [],
    WR: [],
    TE: []
  };

  lineupRoster.forEach(
    (projection) => {
      const position =
        String(
          projection.position || ""
        ).toUpperCase();

      if (!groups[position]) {
        return;
      }

      groups[position].push(
        projection
      );
    }
  );

  Object.values(groups).forEach(
    (players) => {
      players.sort(
        (a, b) =>
          Number(
            b.projected_ppr
          ) -
          Number(
            a.projected_ppr
          )
      );
    }
  );

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
function getLineupPlayerAiData(
  projection
) {
  const matchedPlayer =
    getProjectionPlayer(
      projection
    );

  if (!matchedPlayer) {
    return {
      score: null,
      rank: null
    };
  }

  const profile = "balanced";

  const position =
    String(
      projection.position || ""
    ).toUpperCase();

  const rankings =
    getPositionRankings(
      position,
      profile
    );

  const matchingEntry =
    rankings.find(
      entry =>
        entry.player ===
        matchedPlayer ||
        normalizeName(
          entry.player?.name
        ) ===
        normalizeName(
          matchedPlayer.name
        )
    );

  const rank =
    getPlayerPositionRank(
      matchedPlayer,
      profile
    );

  const score =
    Number(
      matchingEntry?.score
    );

  return {
    score:
      Number.isFinite(score)
        ? score
        : null,

    rank:
      Number.isFinite(
        Number(rank)
      )
        ? Number(rank)
        : null
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
          if (
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


function renderStartSitInsights(
  slots,
  bench
) {
  const insights =
    getStartSitInsights(
      slots,
      bench
    );

  if (insights.length === 0) {
    return null;
  }

  const section =
    document.createElement(
      "section"
    );

  section.className =
    "start-sit-insights";

  const heading =
    document.createElement("div");

  heading.className =
    "start-sit-insights-heading";

  heading.innerHTML = `
    <span class="eyebrow">
      AI SECOND OPINION
    </span>

    <h4>
      Start/Sit Insights
    </h4>

    <p>
      Projected PPR determines the optimal lineup.
      These alerts highlight close decisions where
      the underlying AI Score favors a bench player.
    </p>
  `;

  section.appendChild(
    heading
  );

  insights.forEach(
    (insight) => {
      const card =
        document.createElement(
          "div"
        );

      card.className =
        "start-sit-insight-card";

      const starterName =
        insight.starter.player_name;

      const benchName =
        insight.benchPlayer.player_name;

      card.innerHTML = `
        <div class="start-sit-insight-label">
          AI EDGE • ${insight.slot}
        </div>

        <div class="start-sit-insight-title">
          Review ${starterName}
          vs. ${benchName}
        </div>

        <p>
          The PPR model starts
          <strong>${starterName}</strong>,
          but the underlying AI Score favors
          <strong>${benchName}</strong>.
        </p>

        <div class="start-sit-comparison">
          <div>
            <span>PROJECTED STARTER</span>

            <strong>
              ${starterName}
            </strong>

            <small>
              ${insight.starterPpr.toFixed(2)}
              PPR • AI
              ${insight.starterAi.score.toFixed(1)}
            </small>
          </div>

          <div>
            <span>AI ALTERNATIVE</span>

            <strong>
              ${benchName}
            </strong>

            <small>
              ${insight.benchPpr.toFixed(2)}
              PPR • AI
              ${insight.benchAi.score.toFixed(1)}
            </small>
          </div>
        </div>

        <div class="start-sit-edge-summary">
          <span>
            Projection edge:
            <strong>
              +${insight.projectionEdge.toFixed(2)}
              PPR ${starterName}
            </strong>
          </span>

          <span>
            AI Score edge:
            <strong>
              +${insight.aiEdge.toFixed(1)}
              ${benchName}
            </strong>
          </span>
        </div>
      `;

      section.appendChild(
        card
      );
    }
  );

  return section;
}

  
function renderOptimizedLineup(
  lineup,
  rules
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
        BEST PROJECTED LINEUP
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


function optimizeLineup() {
  const result =
    document.getElementById(
      "lineupAnalyzerResult"
    );

  if (!result) {
    return;
  }

  const rules =
    getLineupRules();

  const groups =
    getLineupPlayersByPosition();

  const bestLineup =
    findBestLegalLineup(
      rules,
      groups
    );

  if (!bestLineup) {
    const missing =
      getMissingLineupNeeds(
        rules,
        groups
      );

    result.innerHTML = `
      <div class="lineup-validation-message">
        <strong>
          Roster is not complete yet.
        </strong>

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

  renderOptimizedLineup(
    bestLineup,
    rules
  );
}

function normalizeName(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/[.'’-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
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

  if (playerWeeklyStatsCache.has(playerName)) {
    return playerWeeklyStatsCache.get(playerName);
  }

  const matches = weeklyStats.filter((row) => {
    const fullName = normalizeName(
      row.player_display_name
    );

    const shortName = normalizeName(
      row.player_name
    );

    return (
      fullName === playerName ||
      fullName.includes(playerName) ||
      playerName.includes(fullName) ||
      shortName === playerName
    );
  });

  playerWeeklyStatsCache.set(playerName, matches);

  return matches;
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

    const total =
      recentGames.reduce(
        (sum, game) =>
          sum + getFantasyPoints(game),
        0
      );

    return total / recentGames.length;
  }

  const playerAverage =
    getRecentAverage(games);

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

    validGames += 1;
  });

  if (validGames === 0) {
    return 50;
  }

  const averageShare =
    totalShare / validGames;

  return Math.max(
    0,
    Math.round(averageShare * 100)
  );
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
    return 50;
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
      Number(positionSignal.sample_size || 0)
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
      Number(matchingEntry.sample_size || 0)
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
    currentTrenchSignals[normalize(player.team)];

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

    opponent: record.defense_team
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

  const fallbackNflId =
    player.nflId ||
    Object.entries(nflPlayerLookup).find(
      ([id, nfl]) => {
        const normalizeTeam = team =>
          ({ LA: "LAR", JAC: "JAX", WSH: "WAS" })[team] || team;

        return (
          normalizeName(player.name) ===
            normalizeName(nfl.name) &&
          player.position === nfl.position &&
          normalizeTeam(player.team) ===
            normalizeTeam(nfl.team)
        );
      }
    )?.[0];
  const rookieScore = fallbackNflId
    ? fantasyAiScores[fallbackNflId]
    : null;
 
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


function getPositionRankings(position, profile) {
  const cacheKey = `${profile}-${position}`;

  if (rankingCache[cacheKey]) {
    return rankingCache[cacheKey];
  }
const relevantPlayers = players.filter((player) => {
  if (player.position !== position) {
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
 * Exclude players whose team does not have
 * a matchup in the current target week.
 *
 * teamNextOpponent only contains teams that
 * are actually playing this week, so a missing
 * matchup represents a bye.
 */
const playerTeam =
  player.team === "LA"
    ? "LAR"
    : player.team;

const weeklyMatchup =
  teamNextOpponent[playerTeam];

if (
  !weeklyMatchup ||
  !weeklyMatchup.opponent ||
  String(weeklyMatchup.opponent)
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
    return (
      (depthOrder >= 1 &&
        depthOrder <= 2) ||
      hasStats
    );
  }

  return false;
});
  const rankings = relevantPlayers
    .map((player) => ({
      player,
      score: calculateScore(player, profile)
    }))
    .sort((a, b) =>
      b.score - a.score ||
      a.player.name.localeCompare(b.player.name)
    );

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

function metricRow(
  label,
  value,
  isRisk = false,
  breakdown = null,
  signalDetails = null
) {
  const info =
    metricDescriptions[label];

  const description = info
    ? info.description
    : "";

  const weight = info
    ? info.weight
    : "";

  const breakdownHtml =
    label === "Model Confidence" &&
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
  signalDetails
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

        ${breakdownHtml}
        
        ${signalDetailsHtml}
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
          ${recommendation}
        </div>
      </div>

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
            ${projectedPpr}
          </div>

          <span class="player-score-rank">
            ${projectedRank}
          </span>
        </div>
      </div>


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
  ${metricRow("Opportunity", metrics.opportunity)}
        ${metricRow("Recent Production", metrics.production)}
        ${metricRow("Usage", metrics.usage)}
        ${metricRow("Matchup", metrics.matchup)}
        ${metricRow(
          "Play Caller Matchup",
          metrics.playCallerMatchup,
          false,
          null,
          playCallerDetails
        )}
        ${metricRow(
          "Player vs Defensive Play Caller",
          metrics.playerVsDefensiveCaller,
          false,
          null,
          playerVsCallerDetails
        )}
        ${metricRow("Red-Zone Usage", metrics.redzone)}

        ${metricRow(
          "Scoring Environment",
          metrics.scoringEnvironment
        )}

        ${metricRow(
          "Model Confidence",
          metrics.expert,
          false,
          confidenceBreakdown
        )}

        ${metricRow("Risk Adjustment", riskAdjustment, true)}

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
          </div>
        </div>
        `}
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
      '<tr><td colspan="7">No ranked players found.</td></tr>';

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

      const opponent =
        matchup?.opponent || "TBD";

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

      const row =
        document.createElement("tr");
      [
        `${player.position}${rank}`,
        player.name,
        opponent,
        score.toFixed(1),
        projectedPpr,
        projectedRank,
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

  // Load Model F PPR projections for that week.
  await loadWeeklyPprProjections();

  // Load the current NFL player pool and connect
  // Sleeper players to NFL/GSIS IDs.
  await loadPlayers();

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
  riskSelect.addEventListener("change", renderPositionRankings);

  // Refresh injury designations every five minutes.
  setInterval(refreshPlayerInjuries, 5 * 60 * 1000);
}

initializeApp();

