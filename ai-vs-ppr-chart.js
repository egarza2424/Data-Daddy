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
  async function initialize() {
    try {
      const response = await fetch("model-validation/ai-vs-ppr-ranking-audit.csv?t=" + Date.now(), {cache:"no-store"});
      if (!response.ok) throw new Error("No published comparison report");
      const rows = csv(await response.text()).filter(r => r.season === "2026" &&
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
