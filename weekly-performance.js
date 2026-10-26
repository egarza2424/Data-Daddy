(function () {
  "use strict";
  const root = document.getElementById("weeklyPerformanceTracker");
  if (!root) return;
  const state = { category: "rankings", position: "ALL", week: null, reports: {} };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const number = value => Number(value);
  const parseCSV = source => {
    const rows = []; let row = [], cell = "", quoted = false;
    for (let i = 0; i < source.length; i++) {
      const c = source[i];
      if (c === '"' && quoted && source[i+1] === '"') { cell += '"'; i++; }
      else if (c === '"') quoted = !quoted;
      else if (c === "," && !quoted) { row.push(cell); cell = ""; }
      else if ((c === "\n" || c === "\r") && !quoted) {
        if (c === "\r" && source[i+1] === "\n") i++;
        row.push(cell); if (row.some(Boolean)) rows.push(row); row=[];cell="";
      } else cell += c;
    }
    row.push(cell); if (row.some(Boolean)) rows.push(row);
    const headers = rows.shift() || [];
    return rows.map(values => Object.fromEntries(headers.map((h,i)=>[h,values[i]||""])));
  };
  async function load(path) {
    const response = await fetch(path + "?t=" + Date.now(), {cache:"no-store"});
    if (!response.ok) throw new Error("Missing report: " + path);
    return parseCSV(await response.text());
  }
  const card = (title, detail, footer) => '<article class="tracker-result-card"><strong>'+esc(title)+'</strong><p>'+esc(detail)+'</p><p>'+esc(footer)+'</p></article>';
  function renderAccuracyChart(rows, week) {
    const chart = document.getElementById("trackerAccuracyChart");
    if (!chart) return;
    const positions = ["QB", "RB", "WR", "TE"];
    const results = positions.map(position => {
      const cohort = rows.filter(r => r.position === position &&
        Number.isFinite(number(r.position_rank)) &&
        Number.isFinite(number(r.actual_ppr)) &&
        r.actual_ppr !== "");
      const cutoff = position === "RB" || position === "WR" ? 24 : 15;
      const sorted = [...cohort].sort((a,b) => number(b.actual_ppr) - number(a.actual_ppr));
      const actualTop = new Set(sorted.slice(0,cutoff).map(r => r.player_id));
      const predictedTop = [...cohort].sort((a,b) => number(a.position_rank) - number(b.position_rank)).slice(0,cutoff);
      const hits = predictedTop.filter(r => actualTop.has(r.player_id)).length;
      const count = predictedTop.length;
      return {position, cutoff, hits, count, pct: count ? 100 * hits / count : null};
    });
    chart.setAttribute("aria-label", "Week " + week + " position-specific ranking overlap: " +
      results.map(r => r.position + " top-" + r.cutoff + " " + (r.pct===null ? "unavailable" : r.pct.toFixed(0)+" percent")).join(", "));
    chart.innerHTML = '<p class="tracker-chart-week">Week '+esc(week)+' · QB/TE top 15 · RB/WR top 24 · completed postgame audit</p>'+
      results.map(r => '<div class="tracker-chart-row"><span class="tracker-chart-label">'+r.position+' <small>Top '+r.cutoff+'</small></span>'+
        '<div class="tracker-chart-track"><div class="tracker-chart-fill" style="width:'+(r.pct??0).toFixed(1)+'%"></div></div>'+
        '<strong class="tracker-chart-value">'+(r.pct===null?'N/A':r.pct.toFixed(0)+'%')+'</strong>'+
        '<small class="tracker-chart-count">'+r.hits+'/'+r.count+'</small></div>').join("")+
      '<p class="tracker-chart-caption">Top-15 QB/TE and top-24 RB/WR overlap uses the matched-player cohort only. Rankings are recalculated within that cohort; missing players are excluded. Higher is better.</p>';
  }
  function render() {
    const {category,position,week,reports}=state;
    root.querySelectorAll("[data-tracker-category]").forEach(b=>{
      b.disabled=b.dataset.trackerCategory===category;
      b.setAttribute("aria-pressed",String(b.disabled));
    });
    const positionSelect=root.querySelector("#trackerPosition");
    positionSelect.value=position;
    const note=root.querySelector("#trackerNote"), list=root.querySelector("#trackerCards");
    let items=[];
    if (category==="rankings" || category==="misses" || category==="sleepers") {
      const all=reports.ranking || [];
      const filtered=all.filter(r=>position==="ALL"||r.position===position);
      // Rank comparisons use the same matched cohort for both predictions and outcomes.
      const enriched=filtered.map(r=>{
        const group=all.filter(x=>x.position===r.position);
        const predicted=group.filter(x=>number(x.position_rank)<number(r.position_rank)).length+1;
        const actual=group.filter(x=>number(x.actual_ppr)>number(r.actual_ppr)).length+1;
        const projection=(reports.projections||[]).find(p=>p.player_id===r.player_id&&p.position===r.position);
        const projectedPpr=projection&&projection.projected_ppr!==""?number(projection.projected_ppr):null;
        return {...r,predicted,actual,delta:Math.abs(predicted-actual),projectedPpr,pprError:projectedPpr===null?null:number(r.actual_ppr)-projectedPpr};
      });
      if (category==="rankings") {
        items=enriched.filter(r=>r.predicted<=15&&r.actual<=15&&r.delta<=3&&number(r.actual_ppr)>=5)
          .sort((a,b)=>a.delta-b.delta||a.predicted-b.predicted).slice(0,12);
      } else if(category==="misses") {
        items=enriched.filter(r=>r.predicted<=30||r.actual<=30)
          .sort((a,b)=>b.delta-a.delta).slice(0,12);
      } else {
        // Sleeper candidates are not identifiable from the ranking-only report.
        const verified=(reports.sleepers||[]).filter(r=>Number(r.target_week)===week&&r.timing_status==="verified_pregame"&&r.result_status==="recorded_game"&&r.sleeper_hit==="True"&&(position==="ALL"||r.position===position));
        note.textContent="Week "+week+" · kickoff-verified frozen sleeper picks: actual PPR ≥ QB 16 / RB-WR 10 / TE 8, and at least 20% above frozen projected PPR. Sleeper Score is not projected PPR.";
        list.innerHTML=verified.sort((a,b)=>number(b.actual_ppr)-number(a.actual_ppr)).slice(0,12).map(r=>card(r.player_name+" · "+r.position,"Sleeper pick #"+r.rank+" · Sleeper Score "+r.sleeper_score,number(r.actual_ppr).toFixed(1)+" actual PPR · "+number(r.ppr_lift_pct).toFixed(1)+"% over projection"+(r.breakout_hit==="True"?" · Breakout":""))).join("")||'<p>No verified sleeper hits are published for this week. This is unavailable data, not zero successful picks.</p>';
        return;
      }
      note.textContent="Week "+week+" · matched-player cohort only. Predicted and actual ranks are recalculated among matched players by position. This is ranking agreement, not PPR projection accuracy.";
      list.innerHTML=items.map(r=>card(r.player_name+" · "+r.position,
        "Predicted #"+r.predicted+" → actual #"+r.actual,
        number(r.actual_ppr).toFixed(1)+" actual PPR"+(r.projectedPpr===null?"": " vs "+r.projectedPpr.toFixed(1)+" projected ("+(r.pprError>=0?"+":"")+r.pprError.toFixed(1)+")")+" · "+r.delta+"-rank difference")).join("")||"<p>No qualifying examples.</p>";
    } else {
      const records=(reports.waiver||[]).filter(r=>Number(r.target_week)===week&&
        r.eligible_for_predictive_accuracy==="True"&&r.result_status==="recorded_game"&&
        r.actual_ppr!==""&&Number.isFinite(number(r.actual_ppr))&&
        (position==="ALL"||r.position===position));
      const minimum={QB:16,RB:10,WR:10,TE:8};
      const hits=records.filter(r=>number(r.actual_ppr)>=(minimum[r.position]??Infinity)).length;
      items=records.sort((a,b)=>number(a.rank)-number(b.rank));
      note.textContent="Week "+week+" · "+hits+"/"+records.length+" verified waiver recommendations met the position PPR threshold (QB 16, RB/WR 10, TE 8). This is a threshold hit rate, not overall prediction accuracy. Unverified recommendations are excluded.";
      list.innerHTML=items.map(r=>{const hit=number(r.actual_ppr)>=(minimum[r.position]??Infinity);
        return card(r.name+" · "+r.position+(hit?" · HIT":" · MISS"),
          "Waiver pick #"+r.rank+" · evidence score "+r.waiver_evidence_score,
          number(r.actual_ppr).toFixed(1)+" actual PPR · threshold "+minimum[r.position]);}).join("")||"<p>No kickoff-verified waiver outcomes published for this week.</p>";
    }
  }
  root.addEventListener("click",event=>{
    const button=event.target.closest("[data-tracker-category]");
    if(button){state.category=button.dataset.trackerCategory;render();}
  });
  root.querySelector("#trackerPosition").addEventListener("change",event=>{state.position=event.target.value;render();});
  async function initialize(){
    const status=root.querySelector("#trackerNote");
    try{
      // Latest completed model-validation report; missing future weeks are not displayed.
      let latest=null, ranking=null;
      for(let week=22;week>=1;week--){
        try { let result; try { result=await load("model-validation/2026-week"+week+"-validation.csv"); } catch(e) { result=await load("model-validation/2026-week"+week+"-provisional-validation.csv"); state.provisional=true; } if(result.length){latest=week;ranking=result;break;} }
        catch(e){continue;}
      }
      if(state.provisional){
        status.textContent="Week "+latest+" preliminary audit suspended: prediction snapshot was not verified as frozen before kickoff.";
        const chart=document.getElementById("trackerAccuracyChart");
        if(chart)chart.textContent="Week "+latest+" accuracy withheld pending pregame snapshot verification. Postgame rankings cannot be scored as predictions.";
        root.querySelector("#trackerCards").innerHTML="<p>Week "+latest+" provisional ranking hits and misses are withheld until kickoff-safe snapshots are validated.</p>";
        return;
      }
      if(!latest) throw new Error("No completed ranking audit found.");
      state.week=latest;state.reports.ranking=ranking;
      if(state.provisional){const label="PRELIMINARY — completed games only; Monday players excluded. ";root.querySelector("#trackerNote").setAttribute("data-audit-status",label);}
      try {state.reports.projections=await load("projection-model/2026-week"+latest+"-ppr-projections.csv");}catch(e){state.reports.projections=[];}
      try {state.reports.comparison=await load("model-validation/ai-vs-ppr-ranking-audit.csv");}catch(e){state.reports.comparison=[];}
      renderAccuracyChart(ranking, latest);
      if(state.provisional){const chartTitle=document.querySelector("#trackerAccuracyChart .tracker-chart-week");if(chartTitle)chartTitle.textContent="Week "+latest+" · PRELIMINARY · Monday players excluded";}
      const chart=document.getElementById("trackerAccuracyChart");
      let comparison=state.reports.comparison.filter(r=>Number(r.week)===latest);
      if(!comparison.length&&state.provisional){
        const cutoffs={QB:24,RB:36,WR:36,TE:24};
        comparison=[];
        for(const pos of Object.keys(cutoffs)){
          const group=ranking.filter(r=>r.position===pos&&r.actual_ppr!=="");
          const cutoff=cutoffs[pos];
          const actualTop=new Set([...group].sort((a,b)=>number(b.actual_ppr)-number(a.actual_ppr)).slice(0,cutoff).map(r=>r.player_id));
          for(const [model,col] of [["AI Rankings","position_rank"],["PPR Projection Rankings","projected_position_rank"]]){
            const rows=group.map(r=>({...r,projected_position_rank:(state.reports.projections.find(p=>p.player_id===r.player_id&&p.position===r.position)||{}).projected_position_rank})).filter(r=>r[col]!==undefined&&r[col]!=="");
            const chosen=rows.sort((a,b)=>number(a[col])-number(b[col])).slice(0,cutoff);
            const hits=chosen.filter(r=>actualTop.has(r.player_id)).length;
            comparison.push({position:pos,model,cutoff,top_group_hits:hits,evaluated_picks:chosen.length,top_group_accuracy_pct:chosen.length?100*hits/chosen.length:0});
          }
        }
      }
      if(chart&&comparison.length){
        const order=["QB","RB","WR","TE"];
        const blocks=order.map(pos=>{
          const group=comparison.filter(r=>r.position===pos);
          if(!group.length)return "";
          return '<div class="tracker-chart-row"><strong>'+pos+' · Top '+group[0].cutoff+'</strong></div>'+group.map(r=>{
            const pct=Math.max(0,Math.min(100,number(r.top_group_accuracy_pct)||0));
            return '<div class="tracker-chart-row"><span class="tracker-chart-label">'+(r.model==="AI Rankings"?"AI Rank":"PPR Rank")+'</span><div class="tracker-chart-track"><div class="tracker-chart-fill" style="width:'+pct+'%"></div></div><strong class="tracker-chart-value">'+pct.toFixed(1)+'%</strong><small class="tracker-chart-count">'+r.top_group_hits+'/'+r.evaluated_picks+'</small></div>';}).join("");
        }).join("");
        chart.innerHTML+='<h5>AI Rankings vs. PPR Rankings — Week '+latest+'</h5>'+blocks+'<p class="tracker-chart-caption">Top-24 QB/TE and top-36 RB/WR. Matched-cohort ranking agreement only; these are not projection accuracy percentages.</p>';
      }
      try {state.reports.sleepers=await load("data/sleeper_validation/sleeper_prediction_audit.csv");}
      catch(e){state.reports.sleepers=[];}
      try {state.reports.waiver=await load("data/waiver_validation/waiver_prediction_audit.csv");}
      catch(e){state.reports.waiver=[];}
      render();
      if(state.provisional){const note=root.querySelector("#trackerNote");note.textContent="PRELIMINARY · Monday players excluded · "+note.textContent;}
    }catch(e){status.textContent="Weekly audit data is not available yet.";const chart=document.getElementById("trackerAccuracyChart");if(chart)chart.textContent="No completed weekly accuracy audit available yet.";root.querySelector("#trackerCards").innerHTML="";}
  }
  initialize();
})();