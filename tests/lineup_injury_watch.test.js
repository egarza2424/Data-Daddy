// Run: node tests/lineup_injury_watch.test.js
// Isolated behavioral checks: no live statuses, projections, or site data are changed.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app.js", "utf8");
const start = source.indexOf("function renderLineupInjuryWatch(");
const end = source.indexOf("\nfunction renderOptimizedLineup(", start);
assert(start >= 0 && end > start, "Injury Watch function not found");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.textContent = ""; }
  appendChild(child) { this.children.push(child); }
}
const context = {
  document: {
    createElement: tag => new Element(tag),
    createTextNode: text => ({ textContent: text })
  },
  getProjectionPlayer: p => p.playerData,
  sleeperInjuryFetchedAt: null
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const render = context.renderLineupInjuryWatch;
const player = (name, position, ppr, status) => ({
  player_name: name, position, projected_ppr: ppr,
  playerData: { injuryStatus: status }
});
const starter = player("Starter", "WR", 16, "QUESTIONABLE");
const backup = player("Backup", "WR", 12, "");
const panel = render([{ slot: "WR1", player: starter }], [backup]);
assert(panel, "Questionable starter must trigger a panel");
const text = JSON.stringify(panel);
assert(text.includes("Starter") && text.includes("QUESTIONABLE"));
assert(text.includes("Backup") && text.includes("4.00 PPR"), "Bench gap must be displayed");
assert.equal(render([{ slot: "WR1", player: player("Healthy", "WR", 16, "") }], [backup]), null);
const doubtful = render([{ slot: "WR1", player: player("Doubtful", "WR", 15, "D") }], []);
assert(JSON.stringify(doubtful).includes("No same-position bench alternative"));
console.log("PASS: questionable starter, bench comparison, healthy starter, doubtful without backup");
