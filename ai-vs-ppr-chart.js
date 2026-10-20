(function () {
  "use strict";
  const root = document.getElementById("modelComparisonChart");
  if (!root) return;
  const safe = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function csv(text) {
    const lines = text.trim().split(/\r?\n/);
    const headers = (lines.shift() || "").split(",");
    return lines.filter(Boolean).map(line => {
      const values = line.split(",");
      return Object.fromEntries(headers.map((key, i) => [key, values[i]]));
    });
  }
  async function loadCSV(path) {
    const response = await fetch(path + "?t=" + Date.now(), {cache:"no-store"});
    if (!response.ok) throw new Error("Missing " + path);
    return csv(await response.text());
  }
  async function fallbackAudit() {
    // Use only completed validation weeks; do not inspect live/future projections.
    for (let week = 22; week >= 1; week--) {
      try {
        const [actual, projections] = await Promise.all([
          loadCSV("model-validation/2026-week" + week + "-validation.csv"),
          loadCSV("projection-model/2026-week" + week + "-ppr-projections.csv")
        ]);
        const projectionMap = new Map(projections.map(r => [r.position + ":" + r.player_id, r]));
        const results = [];
        for (const position of ["QB", "RB", "WR", "TE"]) {
          const cutoff = position === "QB" || position === "TE" ? 24 : 36;
          const cohort = actual.filter(r => r.position === position &&
            r.actual_ppr !== "" && Number.isFinite(Number(r.actual_ppr)) &&
            Number.isFinite(Number(r.position_rank)) &&
            projectionMap.has(r.position + ":" + r.player_id) &&
            Number.isFinite(Number(projectionMap.get(r.position + ":" + r.player_id).projected_position_rank)));
          if (!cohort.length) throw new Error("Incomplete position " + position);
          const sortedActual = [...cohort].sort((a,b) =>
            Number(b.actual_ppr)-Number(a.actual_ppr) || a.player_id.localeCompare(b.player_id));
          const actualTop = new Set(sortedActual.slice(0,cutoff).map(r => r.player_id));
          for (const [model,rank] of [
            ["AI Rankings",r => Number(r.position_rank)],
            ["PPR Projection Rankings",r => Number(projectionMap.get(r.position+":"+r.player_id).projected_position_rank)]
          ]) {
            const picks = [...cohort].sort((a,b) => rank(a)-rank(b) ||
              a.player_id.localeCompare(b.player_id)).slice(0,cutoff);
            results.push({season:"2026",week:String(week),position,model,
              top_group_hits:String(picks.filter(r => actualTop.has(r.player_id)).length),
              evaluated_picks:String(picks.length)});
          }
        }
        return results;
      } catch (error) {
        // Missing or incomplete week: continue to the latest earlier completed week.
      }
    }
    throw new Error("No completed head-to-head data available");
  }
  async function initialize() {
    try {
      let rows;
      try {
        rows = await loadCSV("model-validation/ai-vs-ppr-ranking-audit.csv");
      } catch (error) {
        rows = await fallbackAudit();
      }
      rows = rows.filter(r => r.season === "2026" &&
        ["QB","RB","WR","TE"].includes(r.position) &&
        ["AI Rankings","PPR Projection Rankings"].includes(r.model));
      const weeks = [...new Set(rows.map(r => Number(r.week)).filter(Number.isFinite))].sort((a,b) => b-a);
      const week = weeks.find(w => ["QB","RB","WR","TE"].every(p =>
        ["AI Rankings","PPR Projection Rankings"].every(m => rows.some(r => Number(r.week) === w && r.position === p && r.model === m))));
      if (week === undefined) throw new Error("No complete four-position comparison");
      const current = rows.filter(r => Number(r.week) === week);
      const positions = ["QB","RB","WR","TE"];
      const totals = {"AI Rankings": {hits:0,n:0}, "PPR Projection Rankings": {hits:0,n:0}};
      let html = '<p class="model-comparison-week">Week '+safe(week)+' · completed postgame results</p>';
      positions.forEach(position => {
        const cutoff = position === "QB" || position === "TE" ? 24 : 36;
        html += '<div class="model-comparison-position"><strong>'+position+' <small>Top '+cutoff+'</small></strong>';
        ["AI Rankings","PPR Projection Rankings"].forEach(model => {
          const r = current.find(x => x.position === position && x.model === model);
          const hits = Number(r.top_group_hits), n = Number(r.evaluated_picks);
          const pct = n > 0 ? 100 * hits/n : 0;
          if (Number.isFinite(hits) && Number.isFinite(n)) {totals[model].hits += hits; totals[model].n += n;}
          html += '<div class="model-comparison-bar-row"><span>'+ (model === "AI Rankings" ? "AI Rank" : "PPR Rank") +'</span>'+
            '<div class="model-comparison-track"><div class="model-comparison-fill '+(model === "AI Rankings" ? "model-comparison-ai" : "model-comparison-ppr")+'" style="width:'+pct.toFixed(1)+'%"></div></div>'+
            '<b>'+pct.toFixed(1)+'%</b><small>'+hits+'/'+n+'</small></div>';
        });
        html += '</div>';
      });
      const ai = totals["AI Rankings"], ppr = totals["PPR Projection Rankings"];
      const aiPct = ai.n ? (100*ai.hits/ai.n).toFixed(1) : "N/A";
      const pprPct = ppr.n ? (100*ppr.hits/ppr.n).toFixed(1) : "N/A";
      html += '<p class="model-comparison-summary">Overall top-group overlap: <strong>AI '+aiPct+'%</strong> ('+ai.hits+'/'+ai.n+') · <strong>PPR '+pprPct+'%</strong> ('+ppr.hits+'/'+ppr.n+')</p>'+
        '<p class="model-comparison-disclaimer">Matched-player top-group overlap, not projected PPR error or a guarantee of future performance. Comparisons use completed weeks only.</p>';
      root.innerHTML = html;
    } catch (error) {
      root.textContent = "The head-to-head accuracy chart will appear after the first completed comparison audit is published.";
    }
  }
  initialize();
})();
