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
function draw(){
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