// Regression checks against the actual calculateScore implementation.
// Run: node tests/rookie_prior_identity.test.js
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app.js", "utf8");
const start = source.indexOf("function calculateScore(player, profile) {");
const end = source.indexOf("\nconst injuryOpportunityCache", start);
assert(start >= 0 && end > start, "calculateScore source boundaries missing");
const context = {
  getMetrics: () => ({
    opportunity: 40, production: 40, usage: 40,
    playCallerMatchup: 40, playerVsDefensiveCaller: 40,
    redzone: 40, matchup: 40, expert: 40, risk: 60
  }),
  BASE_WEIGHTS: {
    opportunity: .1674, production: .2046, usage: .1395,
    playCallerMatchup: .0651, playerVsDefensiveCaller: .0651,
    redzone: .093, matchup: .093, expert: .0558, risk: .0465
  },
  riskProfiles: {},
  getTrenchMatchup: () => null,
  getScoringEnvironment: () => null,
  snapshotWeek: 7,
  calculateInjuryOpportunityBoost: () => 0,
  normalizeName: name => String(name || "").toLowerCase().replace(/\\s+(jr|sr|ii|iii)$/i, "").trim(),
  nflPlayerLookup: {
    "00-0041511": { name: "Omar Cooper Jr.", position: "WR", team: "NYJ" }
  },
  fantasyAiScores: {
    "00-0041511": {
      available: true,
      rookie_prior_adjustment: {
        eligible: true, applied: true, prior_score: 80, weight: .25
      }
    }
  },
  window: {},
  getProductionGameCount: () => 2,
  console
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const player = {
  id: "13276", nflId: "13276", name: "Omar Cooper",
  position: "WR", team: "NYJ", status: "Active", injuryStatus: ""
};
assert.equal(context.calculateScore(player, "balanced"), 50,
  "Synthetic Sleeper ID should resolve valid GSIS rookie prior");
context.fantasyAiScores["00-0041511"].rookie_prior_adjustment.eligible = false;
assert.equal(context.calculateScore(player, "balanced"), 40,
  "Ineligible prior must not modify live score");
context.fantasyAiScores["00-0041511"].rookie_prior_adjustment.eligible = true;
context.fantasyAiScores["00-0041511"].rookie_prior_adjustment.applied = false;
assert.equal(context.calculateScore(player, "balanced"), 40,
  "Unapplied prior must not modify live score");
context.fantasyAiScores["00-0041511"].rookie_prior_adjustment.applied = true;
assert.equal(context.calculateScore({...player, team: "BUF"}, "balanced"), 40,
  "Team mismatch must not borrow another player's rookie prior");
console.log("PASS: rookie ID fallback, eligible prior, ineligible/unapplied prior, team isolation");
