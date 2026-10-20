// Run: node tests/lineup_strategies.test.js
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app.js", "utf8");
function extract(start, end) {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, "Could not isolate " + start);
  return source.slice(a, b);
}
const code = extract("function getLineupDistributions(", "\nfunction buildLineupSlots(") +
  "\n" + extract("function getSaferLineupGroups(", "\nfunction optimizeLineup(");
const ctx = { getProjectionPlayer: p => p.playerData };
vm.createContext(ctx);
vm.runInContext(code, ctx);
const p = (name, position, ppr, injuryStatus = "") => ({
  player_name: name, position, projected_ppr: ppr,
  playerData: { injuryStatus }
});
const rules = { QB: 1, RB: 1, WR: 1, TE: 1, FLEX: 1, SUPERFLEX: 0 };
const groups = {
  QB: [p("QB", "QB", 20)],
  RB: [p("Risky RB", "RB", 18, "QUESTIONABLE"), p("Healthy RB", "RB", 13)],
  WR: [p("Risky WR", "WR", 17, "DOUBTFUL"), p("Healthy WR", "WR", 12), p("Flex WR", "WR", 11)],
  TE: [p("TE", "TE", 10)]
};
const best = ctx.findBestLegalLineup(rules, groups);
const safer = ctx.findBestLegalLineup(rules, ctx.getSaferLineupGroups(groups));
assert(best && safer, "Both strategies must form legal lineups");
assert.equal(best.total, 78);
assert.equal(safer.total, 66);
const selectedSafe = Object.values(safer.selected).flat();
assert(selectedSafe.every(x => !["QUESTIONABLE", "DOUBTFUL"].includes(x.playerData.injuryStatus)));
assert.equal(ctx.findBestLegalLineup(rules, ctx.getSaferLineupGroups({
  ...groups, QB: [p("Only QB", "QB", 20, "Q")]
})), null, "Safer strategy must not invent eligible players");
assert.equal(best.total, 78, "Original projections must remain unchanged");
console.log("PASS: maximum PPR, safer legal lineup, injury exclusion, no legal safer lineup");

assert(source.includes('renderOptimizedLineup(bestLineup, rules, useSafer ? "safe" : "best")'),
  "Selected strategy must be passed to the lineup renderer");
assert(source.includes('strategy === "safe" ? "SAFER LINEUP'),
  "Safer mode must display its own heading");
assert(source.includes('button.addEventListener("click", () => optimizeLineup(choice))'),
  "Strategy buttons must rerender the selected lineup");
assert(source.includes('const starterKeys =') && source.includes('!starterKeys.has('),
  "Bench must be rebuilt from the selected lineup starters");
console.log("PASS: strategy controls, heading, and bench rendering wiring");
