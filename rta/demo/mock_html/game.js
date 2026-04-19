"use strict";

const SUITS = ["s", "h", "d", "c"];
const RANKS = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"];

const SCRIPT = [
  { street: "preflop", hero: ["As","Kd"], villain: ["Qc","Qh"], board: [], pot: 300, heroStack: 9850, villainStack: 9700, heroBet: 150, villainBet: 300, btn: "hero", heroTurn: true, actions: ["Fold","Call","Raise 450"] },
  { street: "flop", hero: ["As","Kd"], board: ["Ah","7c","2d"], pot: 600, heroStack: 9700, villainStack: 9700, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: false, actions: [] },
  { street: "flop", hero: ["As","Kd"], board: ["Ah","7c","2d"], pot: 900, heroStack: 9700, villainStack: 9400, heroBet: 0, villainBet: 300, btn: "hero", heroTurn: true, actions: ["Fold","Call","Raise 900"] },
  { street: "turn", hero: ["As","Kd"], board: ["Ah","7c","2d","9s"], pot: 1200, heroStack: 9400, villainStack: 9400, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: true, actions: ["Check","Bet 600"] },
  { street: "river", hero: ["As","Kd"], board: ["Ah","7c","2d","9s","3h"], pot: 1200, heroStack: 9400, villainStack: 9400, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: true, actions: ["Check","Bet 800"] },
];

let step = 0;

function render(state) {
  document.getElementById("hero-card-1").textContent = state.hero[0];
  document.getElementById("hero-card-2").textContent = state.hero[1];
  const board = document.getElementById("board");
  board.innerHTML = "";
  for (const c of state.board) {
    const div = document.createElement("div");
    div.className = "card";
    div.textContent = c;
    board.appendChild(div);
  }
  document.getElementById("pot").textContent = String(state.pot);
  document.getElementById("hero-stack").textContent = String(state.heroStack);
  document.getElementById("villain-stack").textContent = String(state.villainStack);
  document.getElementById("hero-bet").textContent = String(state.heroBet);
  document.getElementById("villain-bet").textContent = String(state.villainBet);
  document.getElementById("button-marker").textContent = state.btn === "hero" ? "D" : "";
  const bar = document.getElementById("action-bar");
  bar.innerHTML = "";
  for (const label of state.actions) {
    const b = document.createElement("button");
    b.textContent = label;
    bar.appendChild(b);
  }
  document.getElementById("hero-action-highlight").classList.toggle("active", state.heroTurn);
}

document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowRight") {
    step = (step + 1) % SCRIPT.length;
    render(SCRIPT[step]);
  } else if (e.key === "ArrowLeft") {
    step = (step - 1 + SCRIPT.length) % SCRIPT.length;
    render(SCRIPT[step]);
  } else if (e.key === "r") {
    step = 0;
    render(SCRIPT[0]);
  }
});

render(SCRIPT[0]);
