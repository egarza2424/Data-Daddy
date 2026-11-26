/* Week 9 D/ST editorial Top 30 — original V1 projections preserved. */
(function(){
"use strict";
const data=[["Denver Broncos","DEN","CAR",6.38],["New Orleans Saints","NO","CLE",6.33],["Cincinnati Bengals","CIN","ATL",6.82],["Houston Texans","HOU","LAC",6.82],["Jacksonville Jaguars","JAX","BAL",6.04],["Tampa Bay Buccaneers","TB","CHI",5.83],["Chicago Bears","CHI","TB",6.31],["Detroit Lions","DET","MIA",6.31],["Green Bay Packers","GB","NE",6.27],["Minnesota Vikings","MIN","BUF",6.02],["Cleveland Browns","CLE","NO",6.03],["Dallas Cowboys","DAL","IND",5.9],["Arizona Cardinals","ARI","SEA",5.84],["Seattle Seahawks","SEA","ARI",5.79],["New England Patriots","NE","GB",5.68],["Buffalo Bills","BUF","MIN",5.54],["Washington Commanders","WAS","LA",5.48],["Atlanta Falcons","ATL","CIN",5.32],["Kansas City Chiefs","KC","NYJ",5.28],["New York Giants","NYG","PHI",5.19],["Las Vegas Raiders","LV","SF",5.02],["Philadelphia Eagles","PHI","NYG",5],["New York Jets","NYJ","KC",4.92],["Los Angeles Chargers","LAC","HOU",4.84],["Los Angeles Rams","LA","WAS",4.78],["San Francisco 49ers","SF","LV",4.74],["Baltimore Ravens","BAL","JAX",4.64],["Carolina Panthers","CAR","DEN",4.53],["Indianapolis Colts","IND","DAL",4.38],["Miami Dolphins","MIA","DET",4.18]];
window.DATA_DADDY_DST_WEEK9 = data.map((row, index) => ({ player_id: "dst:" + row[1], player_name: row[0] + " D/ST", position: "DST", team: row[1], opponent: row[2], projected_ppr: row[3], projected_position_rank: index + 1, snapshot_week: 9, projection_model: "DST_V1_editorial_order" }));
const actualScores={}; // Week 9 actuals pending.
const dstButton=document.querySelector("[data-dst-projection]");
const dstPanel=document.getElementById("dstProjectionPanel");
const playerWrapper=document.getElementById("playerProjectionWrapper");
const pagination=document.getElementById("projectionPagination");
const search=document.getElementById("projectionSearch");
const table=document.getElementById("dstProjectionTableBody");
const cards=document.getElementById("dstProjectionMobileCards");
if(!dstButton||!dstPanel||!playerWrapper||!pagination||!table||!cards)return;
let selected=false;
const week12Editorial=[{"rank":1,"name":"Houston Texans","team":"HOU","opponent":"vs. BAL","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":2,"name":"Minnesota Vikings","team":"MIN","opponent":"vs. ATL","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":3,"name":"Jacksonville Jaguars","team":"JAC","opponent":"vs. TEN","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":4,"name":"New York Giants","team":"NYG","opponent":"@ IND","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":5,"name":"Denver Broncos","team":"DEN","opponent":"@ PIT","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":6,"name":"Tampa Bay Buccaneers","team":"TB","opponent":"vs. CAR","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":7,"name":"Washington Commanders","team":"WAS","opponent":"@ ARI","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":8,"name":"New York Jets","team":"NYJ","opponent":"@ MIA","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":9,"name":"Dallas Cowboys","team":"DAL","opponent":"vs. PHI","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":10,"name":"Cleveland Browns","team":"CLE","opponent":"vs. LV","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":11,"name":"Los Angeles Rams","team":"LAR","opponent":"vs. GB","projected_ppr":null,"model_score":null,"status":"Completed — post-kickoff editorial; exclude from pregame audit"},{"rank":12,"name":"New England Patriots","team":"NE","opponent":"@ LAC","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":13,"name":"Los Angeles Chargers","team":"LAC","opponent":"vs. NE","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":14,"name":"San Francisco 49ers","team":"SF","opponent":"vs. SEA","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":15,"name":"Cincinnati Bengals","team":"CIN","opponent":"vs. NO","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":16,"name":"Pittsburgh Steelers","team":"PIT","opponent":"vs. DEN","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":17,"name":"Green Bay Packers","team":"GB","opponent":"@ LAR","projected_ppr":null,"model_score":null,"status":"Completed — post-kickoff editorial; exclude from pregame audit"},{"rank":18,"name":"Miami Dolphins","team":"MIA","opponent":"vs. NYJ","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":19,"name":"Carolina Panthers","team":"CAR","opponent":"@ TB","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":20,"name":"Las Vegas Raiders","team":"LV","opponent":"@ CLE","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":21,"name":"Seattle Seahawks","team":"SEA","opponent":"@ SF","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":22,"name":"Kansas City Chiefs","team":"KC","opponent":"@ BUF","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":23,"name":"Buffalo Bills","team":"BUF","opponent":"vs. KC","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"},{"rank":24,"name":"Chicago Bears","team":"CHI","opponent":"@ DET","projected_ppr":null,"model_score":null,"status":"Editorial — kickoff status not independently confirmed"}];
function draw(){
 const week=Number(document.documentElement.dataset.targetWeek);
 const note=dstPanel.querySelector(".dst-projection-note");
 if(week===12){
 if(note)note.textContent="Week 12 · Editorial Top 24 D/ST rankings · Original Week 12 model projections unavailable; completed games excluded from pregame audit.";
 const q=(search?.value||"").trim().toLowerCase();
 table.replaceChildren();cards.replaceChildren();
 for(const r of week12Editorial.filter(r=>(r.name+" "+r.team+" "+r.opponent).toLowerCase().includes(q))){
 const tr=document.createElement("tr");for(const v of [r.rank,r.name,"—","D/ST",r.team,r.opponent,"—",r.status]){const td=document.createElement("td");td.textContent=String(v);tr.appendChild(td);}table.appendChild(tr);
 const card=document.createElement("div");card.className="projection-mobile-card";const heading=document.createElement("strong");heading.textContent="#"+r.rank+" "+r.name;const details=document.createElement("p");details.textContent=r.opponent+" · "+r.status+" · Projected points: —";card.append(heading,details);cards.appendChild(card);
 }return;
 }
 if(note)note.textContent="Week 9 · Editorial Top 30 D/ST rankings · Original experimental V1 projected points preserved."; 

 const q=(search?.value||"").trim().toLowerCase();
 const list=data.filter(r=>(r[0]+" "+r[1]+" "+r[2]+" D/ST").toLowerCase().includes(q));
 table.replaceChildren();cards.replaceChildren();
 for(const r of list){
  const tr=document.createElement("tr");
  for(const v of [data.indexOf(r)+1,r[0],r[3].toFixed(2),"D/ST",r[1],r[2],Object.prototype.hasOwnProperty.call(actualScores,r[1])?actualScores[r[1]].toFixed(2):"—","Editorial Week 9"]){
   const td=document.createElement("td");td.textContent=String(v);tr.appendChild(td);
  }table.appendChild(tr);
  const card=document.createElement("div");card.className="projection-mobile-card";
  const heading=document.createElement("strong");heading.textContent="#"+(data.indexOf(r)+1)+" "+r[0];
  const details=document.createElement("p");details.textContent="D/ST · "+r[1]+" vs "+r[2]+" · "+r[3].toFixed(2)+" projected pts · Actual D/ST: "+(Object.prototype.hasOwnProperty.call(actualScores,r[1])?actualScores[r[1]].toFixed(2):"—");
  card.append(heading,details);cards.appendChild(card);
 }
 if(!list.length){const tr=document.createElement("tr");const td=document.createElement("td");td.colSpan=8;td.textContent="No matching D/ST projections.";tr.appendChild(td);table.appendChild(tr);}
}
function setDst(active){
 selected=active;dstPanel.hidden=!active;playerWrapper.hidden=active;pagination.hidden=active;
 dstButton.classList.toggle("active",active);dstButton.setAttribute("aria-pressed",String(active));
 if(active){document.querySelectorAll("[data-projection-position]").forEach(b=>b.classList.remove("active"));draw();}
}
dstButton.addEventListener("click",()=>setDst(true));
document.querySelectorAll("[data-projection-position]").forEach(b=>b.addEventListener("click",()=>setDst(false)));
search?.addEventListener("input",()=>{if(selected)draw();});
})();