
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
        throw new Error("Incomplete Week 6 ranking comparison");
      }

      let html =
        '<p class="model-comparison-week">' +
        'Week ' + safe(latestWeek) + ' · ' +
        safe(latestSeason) +
        ' · Verified-player comparison</p>';

      html += '<p class="model-comparison-disclaimer">' +
        'Top-group hits are provisional. Missing player results are ' +
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
          const verified = Number(r.verified_players);
          const selected = Number(r.selected_players);
          const coverage = selected > 0
            ? 100 * verified / selected : 0;
          const pct = 100 * hits / cutoff;

          if (![hits, verified, selected, pct].every(Number.isFinite)) {
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
              'Verified selections: ' + verified + '/' + selected +
              ' (' + coverage.toFixed(1) + '%)' +
            '</p>';
        }

        html += '</div>';
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
