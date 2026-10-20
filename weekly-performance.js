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
  const card = (title, detail, footer) => '<article class="launch-tool-card" style="display:block;padding:16px;min-width:0"><strong>'+esc(title)+'</strong><p>'+esc(detail)+'</p><p>'+esc(footer)+'</p></article>';
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
        return {...r,predicted,actual,delta:Math.abs(predicted-actual)};
      });
      if (category==="rankings") {
        items=enriched.filter(r=>r.predicted<=15&&r.actual<=15&&r.delta<=3&&number(r.actual_ppr)>=5)
          .sort((a,b)=>a.delta-b.delta||a.predicted-b.predicted).slice(0,12);
      } else if(category==="misses") {
        items=enriched.filter(r=>r.predicted<=30||r.actual<=30)
          .sort((a,b)=>b.delta-a.delta).slice(0,12);
      } else {
        // Sleeper candidates are not identifiable from the ranking-only report.
        note.textContent="Sleeper results require a separately frozen, pregame sleeper recommendation file linked to actual PPR. Rankings alone cannot establish a sleeper hit.";
        list.innerHTML='<p>No independently verified sleeper hits available in the published audit.</p>';
        return;
      }
      note.textContent="Week "+week+" · matched-player cohort only. Predicted and actual ranks are recalculated among matched players by position. This is ranking agreement, not PPR projection accuracy.";
      list.innerHTML=items.map(r=>card(r.player_name+" · "+r.position,
        "Predicted #"+r.predicted+" → actual #"+r.actual,
        number(r.actual_ppr).toFixed(1)+" PPR · "+r.delta+"-rank difference")).join("")||"<p>No qualifying examples.</p>";
    } else {
      items=(reports.waiver||[]).filter(r=>Number(r.target_week)===week&&
        r.eligible_for_predictive_accuracy==="True"&&r.result_status==="recorded_game"&&
        Number.isFinite(number(r.actual_ppr))&&number(r.actual_ppr)>=10&&
        (position==="ALL"||r.position===position))
        .sort((a,b)=>number(b.actual_ppr)-number(a.actual_ppr)).slice(0,12);
      note.textContent="Week "+week+" · verified pregame waiver recommendations with recorded results and at least 10 PPR. This is a display threshold, not a validated prediction-accuracy metric.";
      list.innerHTML=items.map(r=>card(r.name+" · "+r.position,
        "Waiver recommendation #"+r.rank+" · evidence score "+r.waiver_evidence_score,
        number(r.actual_ppr).toFixed(1)+" actual PPR")).join("")||"<p>No qualifying verified waiver results for this week.</p>";
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
        try { const result=await load("model-validation/2026-week"+week+"-validation.csv");if(result.length){latest=week;ranking=result;break;} }
        catch(e){continue;}
      }
      if(!latest) throw new Error("No completed ranking audit found.");
      state.week=latest;state.reports.ranking=ranking;
      try {state.reports.waiver=await load("data/waiver_validation/waiver_prediction_audit.csv");}
      catch(e){state.reports.waiver=[];}
      render();
    }catch(e){status.textContent="Weekly audit data is not available yet.";root.querySelector("#trackerCards").innerHTML="";}
  }
  initialize();
})();