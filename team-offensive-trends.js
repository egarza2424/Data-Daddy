/* Data Daddy Team Offensive Trends: observed target distribution, not personnel-package estimates. */
(async function () {
  const root = document.getElementById("teamOffensiveTrends");
  if (!root) return;
  const status = root.querySelector("[data-status]");
  const select = root.querySelector("[data-team]");
  const output = root.querySelector("[data-results]");
  const fmt = n => Number.isFinite(n) ? n.toFixed(1) + "%" : "N/A";
  try {
    const response = await fetch("./nfl-stats.json", {cache:"no-cache"});
    if (!response.ok) throw new Error("Stats feed unavailable");
    const payload = await response.json();
    if (!Array.isArray(payload.players)) throw new Error("Missing player-week stats");
    const rows = payload.players.filter(p =>
      Number(p.season) === 2026 && Number(p.week) >= 1 &&
      ["REG", undefined, null].includes(p.season_type) &&
      ["WR","TE","RB"].includes(p.position) &&
      Number.isFinite(Number(p.targets)) && p.team
    );
    if (!rows.length) throw new Error("No verified 2026 target data");
    const maxWeek = Math.max(...rows.map(p => Number(p.week)));
    const weeks = [...new Set(rows.map(p => Number(p.week)))].sort((a,b)=>a-b);
    const latest = weeks.slice(-3);
    const earlier = weeks.slice(0,-3);
    const teams = [...new Set(rows.map(p => p.team))].sort();
    select.replaceChildren(...teams.map(t => {
      const option = document.createElement("option"); option.value=t; option.textContent=t; return option;
    }));
    select.value = teams.includes("LA") ? "LA" : teams.includes("LAR") ? "LAR" : teams[0];
    function summary(team, windowWeeks) {
      const relevant = rows.filter(p => p.team === team && windowWeeks.includes(Number(p.week)));
      const totals = {WR:0,TE:0,RB:0};
      for (const p of relevant) totals[p.position] += Math.max(0,Number(p.targets));
      const total = Object.values(totals).reduce((a,b)=>a+b,0);
      const byWeek = [...new Set(relevant.map(p=>Number(p.week)))].length;
      return {total,byWeek,totals,share:total ? 100*totals.TE/total : NaN};
    }
    function render() {
      const team=select.value, recent=summary(team,latest), prior=summary(team,earlier);
      output.replaceChildren();
      const headline=document.createElement("h3"); headline.textContent=team+" — receiving target distribution"; output.append(headline);
      const detail=document.createElement("p");
      detail.textContent="Latest "+recent.byWeek+" observed week(s): "+latest.join(", ")+". Targets: "+recent.total+".";
      output.append(detail);
      const grid=document.createElement("div"); grid.className="team-trends-grid";
      for(const pos of ["TE","WR","RB"]) {
        const box=document.createElement("div");box.className="team-trend-stat";
        const share=recent.total ? 100*recent.totals[pos]/recent.total : NaN;
        const title=document.createElement("strong");title.textContent=pos+" target share";
        const value=document.createElement("span");value.textContent=fmt(share);
        const count=document.createElement("small");count.textContent=recent.totals[pos]+" targets";
        box.append(title,value,count);grid.append(box);
      }
      output.append(grid);
      const trend=document.createElement("p");
      if(prior.total && recent.total) {
        const delta=recent.share-prior.share;
        trend.textContent="TE share trend: "+fmt(prior.share)+" in earlier weeks → "+fmt(recent.share)+" in latest three ("+(delta>=0?"+":"")+delta.toFixed(1)+" percentage points).";
      } else trend.textContent="TE share trend: insufficient earlier-week target data for comparison.";
      output.append(trend);
      const note=document.createElement("p");note.className="team-trends-note";
      note.textContent="Observed team target shares only. These are NOT 12/13-personnel rates, route participation, or injury-adjusted projections. Target totals depend on feed completeness. No model rankings or PPR values are changed by this panel.";
      output.append(note);
    }
    select.addEventListener("change",render);
    status.textContent="2026 observed targets through Week "+maxWeek+" · last three available weeks compared with earlier weeks";
    render();
  } catch(error) {
    status.textContent="Team target trends unavailable: "+error.message;
  }
})();
