
(function () {
  "use strict";

  const root = document.getElementById("modelComparisonChart");
  if (!root) return;

  const safe = value => String(value ?? "").replace(
    /[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])
  );

  async function loadJSON(path) {
    const response = await fetch(path + "?t=" + Date.now(), {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error("Missing " + path);
    }

    return response.json();
  }

  async function initialize() {
    try {
      const rows = await loadJSON(
        "data/weekly-ranking-accuracy.json"
      );

      const latestWeek = Math.max(
        ...rows.map(r => Number(r.week))
      );

      const latestSeason = Math.max(
        ...rows
          .filter(r => Number(r.week) === latestWeek)
          .map(r => Number(r.season))
      );

      const positions = ["QB", "RB", "WR", "TE"];
      const methods = ["AI Score", "Projected PPR"];
      const valid = rows.filter(r =>
        Number(r.week) === latestWeek &&
        Number(r.season) === latestSeason &&
        positions.includes(r.position) &&
        methods.includes(r.method)
      );

      if (valid.length !== 8) {
        throw new Error("Incomplete weekly ranking comparison");
      }

      let html =
        '<p class="model-comparison-week">' +
        'Week ' + safe(latestWeek) + ' · ' +
        safe(latestSeason) +
        ' · Verified-player comparison</p>';

      html += '<p class="model-comparison-disclaimer">' +
        'Top-group hits are provisional confirmed counts; percentages use the target cutoff. Missing player results are ' +
        'not counted as verified misses.</p>';

      for (const position of positions) {
        const cutoff = position === "QB" || position === "TE" ? 24 : 36;

        html += '<div class="model-comparison-position">' +
          '<strong>' + position + ' <small>Top ' + cutoff +
          '</small></strong>';

        for (const method of methods) {
          const r = valid.find(
            x => x.position === position && x.method === method
          );

          if (!r || Number(r.top_n) !== cutoff) {
            throw new Error("Invalid comparison for " + position);
          }

          const hits = Number(r.top_n_hits);
          const verified = r.verified_players == null ? null : Number(r.verified_players);
          const selected = Number(r.selected_players);
          const coverage = r.verified_players == null ? null : (selected > 0 ? 100 * verified / selected : 0);
          const pct = 100 * hits / cutoff;

          if (![hits, selected, pct].every(Number.isFinite) || (verified !== null && !Number.isFinite(verified))) {
            throw new Error("Invalid comparison values");
          }

          html +=
            '<div class="model-comparison-bar-row">' +
              '<span>' + (method === "AI Score" ? "AI Rank" : "PPR Rank") +
              '</span>' +
              '<div class="model-comparison-track">' +
                '<div class="model-comparison-fill ' +
                  (method === "AI Score"
                    ? "model-comparison-ai"
                    : "model-comparison-ppr") +
                  '" style="width:' + pct.toFixed(1) + '%"></div>' +
              '</div>' +
              '<b>' + pct.toFixed(1) + '%</b>' +
              '<small>' + hits + '/' + cutoff + '</small>' +
            '</div>' +
            '<p class="model-comparison-disclaimer">' +
              'Verified selections: ' + (coverage === null ? 'pending reconciliation' : verified + '/' + selected + ' (' + coverage.toFixed(1) + '%)') +
            '</p>';
        }

        html += '</div>';
      }

      // Week 7 rank-error audit uses the frozen Oct 22 snapshot and matched
      // union of either method's top cutoff. This is not a top-hit percentage.
      if (latestSeason === 2026 && latestWeek === 7) {
        const rankError = {
          QB: {ai:7.000, ppr:7.280, matched:25, unresolved:0},
          TE: {ai:13.115, ppr:13.923, matched:26, unresolved:1},
          RB: {ai:14.588, ppr:13.059, matched:34, unresolved:4},
          WR: {ai:17.472, ppr:19.139, matched:36, unresolved:6}
        };
        html += '<section class="model-comparison-rank-error">' +
          '<h5>Average Ranking Error · Week 7</h5>' +
          '<p class="model-comparison-disclaimer">Mean absolute positional rank error; lower is better. Matched players selected in either model\'s top group. Provisional: unmatched players are excluded.</p>' +
          '<table><thead><tr><th>Position</th><th>AI Score</th><th>Projected PPR</th><th>Matched</th></tr></thead><tbody>';
        for (const position of positions) {
          const r = rankError[position];
          html += '<tr><th>' + position + '</th><td>' + r.ai.toFixed(2) +
            '</td><td>' + r.ppr.toFixed(2) + '</td><td>' + r.matched +
            '</td></tr>';
        }
        html += '</tbody></table><p class="model-comparison-disclaimer">' +
          'WR warning: three fringe players (Dominic Lovett, Xavier Gipson, Malik Turner) were incorrectly selected in AI\'s top 36. They are documented selection errors, but are not assigned invented actual ranks or PPR points. The WR ranking-error result does not capture those mistakes.</p></section>';
      }

      html += '<p class="model-comparison-disclaimer">' +
        'Percentages show provisional top-group overlap among ' +
        'verified results, not overall prediction accuracy. ' +
        'AI Score and Projected PPR selections were evaluated independently.' +
        '</p>';

      root.innerHTML = html;

    } catch (error) {
      root.textContent =
        "The latest verified ranking comparison is unavailable.";
      console.error("Data Daddy ranking chart:", error);
    }
  }

  initialize();
})();
