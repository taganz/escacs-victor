"use strict";

// The server owns the game. This page draws the state it sends, counts the
// clocks down between messages and sends the user's actions.

const FILES = "abcdefgh";
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const LOW_TIME = 20;

const $ = (id) => document.getElementById(id);
const boardEl = $("board");

let socket = null;
let state = null;          // last "state" message
let receivedAt = 0;        // performance.now() when it arrived
let selected = null;       // selected square, e.g. "e2"
let pending = null;        // move sent and not yet confirmed, e.g. "e2e4"
let drag = null;           // current drag
let shownResultFor = null; // so the result is announced only once

// --- Connection -----------------------------------------------------------

// The id of this browser's game, so a reload gets back to it.
const GAME_KEY = "escacs-victor-game";

function storedGameId() {
  try {
    return localStorage.getItem(GAME_KEY) || "";
  } catch {
    return "";
  }
}

function storeGameId(id) {
  try {
    if (id) localStorage.setItem(GAME_KEY, id);
  } catch {
    // Without storage a reload just starts over.
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const game = encodeURIComponent(storedGameId());
  socket = new WebSocket(`${proto}://${location.host}/ws?game=${game}`);
  socket.onmessage = (event) => onMessage(JSON.parse(event.data));
  socket.onclose = () => {
    setStatus("Sin conexión con el servidor. Reintentando…");
    setTimeout(connect, 2000);
  };
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

function onMessage(message) {
  if (message.type === "state") {
    state = message;
    storeGameId(message.game_id);
    receivedAt = performance.now();
    pending = null;
    selected = null;
    render();
  } else if (message.type === "error" || message.type === "notice") {
    toast(message.message);
  }
}

// --- Rendering ------------------------------------------------------------

function game() {
  return state && state.game;
}

function orientation() {
  return game() ? game().user_color : "white";
}

function render() {
  const g = game();
  $("provisional").hidden = !(state && state.provisional_bot);
  renderBoard();
  renderPlayers();
  renderMoves();
  renderStatus();
  renderResult();
  $("fen").value = g ? g.fen : START_FEN;
  $("btn-resign").disabled = !g || g.status !== "playing";
  if (!g && !$("color-dialog").open) openColorDialog(false);
}

function parsePlacement(fen) {
  const pieces = {};
  fen.split(" ")[0].split("/").forEach((row, i) => {
    const rank = 8 - i;
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) file += Number(ch);
      else pieces[FILES[file++] + rank] = ch;
    }
  });
  return pieces;
}

function pieceId(ch) {
  return (ch === ch.toUpperCase() ? "w" : "b") + ch.toLowerCase();
}

function pieceSvg(ch) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 40 40");
  svg.classList.add("piece");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `pieces.svg#${pieceId(ch)}`);
  svg.appendChild(use);
  return svg;
}

function squaresInOrder() {
  const white = orientation() === "white";
  const list = [];
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const file = white ? col : 7 - col;
      const rank = white ? 8 - row : row + 1;
      list.push({ name: FILES[file] + rank, file, rank, row, col });
    }
  }
  return list;
}

function legalMoves() {
  const g = game();
  return g && g.status === "playing" && !pending ? g.legal_moves : [];
}

function destinationsFrom(square) {
  return legalMoves().filter((m) => m.startsWith(square)).map((m) => m.slice(2, 4));
}

function renderBoard() {
  const g = game();
  const pieces = parsePlacement(g ? g.fen : START_FEN);
  if (pending) {
    const from = pending.slice(0, 2), to = pending.slice(2, 4);
    pieces[to] = pieces[from];
    delete pieces[from];
  }
  const last = pending || (g && g.last_move);
  const dests = selected ? destinationsFrom(selected) : [];

  boardEl.replaceChildren();
  for (const sq of squaresInOrder()) {
    const el = document.createElement("div");
    el.className = "sq " + ((sq.file + sq.rank) % 2 === 0 ? "light" : "dark");
    el.dataset.square = sq.name;
    if (last && (last.slice(0, 2) === sq.name || last.slice(2, 4) === sq.name)) el.classList.add("last");
    if (selected === sq.name) el.classList.add("selected");
    if (g && !pending && g.check === sq.name) el.classList.add("check");
    if (dests.includes(sq.name)) {
      el.classList.add("dest");
      if (pieces[sq.name]) el.classList.add("capture");
    }
    if (sq.col === 7) el.appendChild(coord("rank", sq.rank));
    if (sq.row === 7) el.appendChild(coord("file", FILES[sq.file]));
    if (pieces[sq.name]) el.appendChild(pieceSvg(pieces[sq.name]));
    boardEl.appendChild(el);
  }
}

function coord(kind, text) {
  const span = document.createElement("span");
  span.className = "coord " + kind;
  span.textContent = text;
  return span;
}

function renderPlayers() {
  const g = game();
  const bottom = orientation();
  const top = bottom === "white" ? "black" : "white";
  const nameOf = (c) => (g ? g[`${c}_name`] : c === "white" ? "user" : "Bot");
  $("name-top").textContent = nameOf(top);
  $("name-bottom").textContent = nameOf(bottom);
  $("bar-top").dataset.color = top;
  $("bar-bottom").dataset.color = bottom;
  $("thinking").hidden = !(state && state.bot_thinking);
  renderClocks();
}

function clockValue(color) {
  const g = game();
  if (!g) return 600;
  let value = g.clock[color];
  if (g.clock.running === color) value -= (performance.now() - receivedAt) / 1000;
  return Math.max(0, value);
}

function formatClock(seconds) {
  if (seconds < 10) {
    const tenths = Math.floor(seconds * 10) / 10;
    return `0:${tenths.toFixed(1).padStart(4, "0")}`;
  }
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function renderClocks() {
  const g = game();
  for (const pos of ["top", "bottom"]) {
    const color = $(`bar-${pos}`).dataset.color;
    const el = $(`clock-${pos}`);
    const value = clockValue(color);
    el.textContent = formatClock(value);
    el.classList.toggle("active", !!g && g.clock.running === color);
    el.classList.toggle("low", !!g && value < LOW_TIME);
  }
}

function renderMoves() {
  const g = game();
  const list = $("moves");
  list.replaceChildren();
  const moves = g ? g.moves : [];
  for (let i = 0; i < moves.length; i += 2) {
    const li = document.createElement("li");
    li.append(span("num", `${i / 2 + 1}.`), span(i === moves.length - 1 ? "latest" : "", moves[i]),
      span(i + 1 === moves.length - 1 ? "latest" : "", moves[i + 1] || ""));
    list.appendChild(li);
  }
  list.scrollTop = list.scrollHeight;
}

function span(cls, text) {
  const s = document.createElement("span");
  if (cls) s.className = cls;
  s.textContent = text;
  return s;
}

function renderStatus() {
  const g = game();
  if (!g) return setStatus("Elige color para empezar.");
  if (g.status === "over") return setStatus("Partida terminada.");
  if (g.turn === g.user_color) setStatus(g.check ? "¡Jaque! Te toca mover." : "Te toca mover.");
  else setStatus("Turno del Bot.");
}

function setStatus(text) {
  $("status").textContent = text;
}

function renderResult() {
  const g = game();
  const box = $("result");
  if (!g || g.status !== "over") {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  let headline = g.result;
  if (g.result === "1/2-1/2") headline = "½-½ · Tablas";
  else if ((g.result === "1-0") === (g.user_color === "white")) headline = `${g.result} · Has ganado`;
  else headline = `${g.result} · Gana el Bot`;
  $("result-score").textContent = headline;
  $("result-reason").textContent = g.reason || "";
  $("result-file").textContent = g.pgn_file ? `Guardada en el servidor como ${g.pgn_file}` : "";
  const link = $("download");
  link.hidden = !state.pgn;
  if (state.pgn) {
    if (link.dataset.pgn !== state.pgn) {
      if (link.href) URL.revokeObjectURL(link.href);
      link.href = URL.createObjectURL(new Blob([state.pgn], { type: "application/x-chess-pgn" }));
      link.dataset.pgn = state.pgn;
    }
    link.download = g.pgn_file || "partida.pgn";
  }
  const key = g.fen + g.result;
  if (shownResultFor !== key) {
    shownResultFor = key;
    toast(`${headline} (${g.reason})`);
  }
}

// --- Moving pieces --------------------------------------------------------

function trySelect(square) {
  if (destinationsFrom(square).length) {
    selected = square;
  } else {
    selected = null;
  }
  renderBoard();
}

function tryMove(from, to) {
  const candidates = legalMoves().filter((m) => m.startsWith(from + to));
  if (!candidates.length) return false;
  if (candidates.length > 1 || candidates[0].length === 5) {
    askPromotion(from, to);
  } else {
    sendMove(candidates[0]);
  }
  return true;
}

function sendMove(uci) {
  pending = uci;
  selected = null;
  send({ type: "move", uci });
  renderBoard();
}

function askPromotion(from, to) {
  const box = $("promotion");
  const white = game().user_color === "white";
  box.replaceChildren();
  for (const p of ["q", "r", "b", "n"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.title = { q: "Dama", r: "Torre", b: "Alfil", n: "Caballo" }[p];
    button.appendChild(pieceSvg(white ? p.toUpperCase() : p));
    button.onclick = (e) => {
      e.stopPropagation();
      box.hidden = true;
      sendMove(from + to + p);
    };
    box.appendChild(button);
  }
  box.onclick = () => {
    box.hidden = true;
    selected = null;
    renderBoard();
  };
  box.hidden = false;
}

function squareAt(x, y) {
  const el = document.elementFromPoint(x, y);
  const sq = el && el.closest(".sq");
  return sq && boardEl.contains(sq) ? sq.dataset.square : null;
}

boardEl.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  const sqEl = e.target.closest(".sq");
  if (!sqEl) return;
  const square = sqEl.dataset.square;

  if (selected && selected !== square && tryMove(selected, square)) return;

  const piece = sqEl.querySelector(".piece");
  if (!piece || !destinationsFrom(square).length) {
    selected = null;
    renderBoard();
    return;
  }

  const wasSelected = selected === square;
  trySelect(square);
  const fresh = boardEl.querySelector(`[data-square="${square}"] .piece`);
  const size = sqEl.getBoundingClientRect().width;
  const ghost = fresh.cloneNode(true);
  ghost.classList.add("dragging");
  ghost.style.width = ghost.style.height = `${size}px`;
  drag = { from: square, ghost, source: fresh, size, wasSelected, moved: false, hover: null };
  moveGhost(e.clientX, e.clientY);
  boardEl.setPointerCapture(e.pointerId);
  e.preventDefault();
});

function moveGhost(x, y) {
  drag.ghost.style.left = `${x - drag.size / 2}px`;
  drag.ghost.style.top = `${y - drag.size / 2}px`;
}

boardEl.addEventListener("pointermove", (e) => {
  if (!drag) return;
  if (!drag.moved) {
    drag.moved = true;
    document.body.appendChild(drag.ghost);
    drag.source.classList.add("ghost");
  }
  moveGhost(e.clientX, e.clientY);
  const over = squareAt(e.clientX, e.clientY);
  if (over !== drag.hover) {
    if (drag.hover) boardEl.querySelector(`[data-square="${drag.hover}"]`)?.classList.remove("hover");
    drag.hover = over;
    if (over) boardEl.querySelector(`[data-square="${over}"]`)?.classList.add("hover");
  }
});

function endDrag(e, cancelled) {
  if (!drag) return;
  const d = drag;
  drag = null;
  d.ghost.remove();
  d.source.classList.remove("ghost");
  if (cancelled) return renderBoard();
  const to = squareAt(e.clientX, e.clientY);
  if (to && to !== d.from && tryMove(d.from, to)) return;
  // A click on an already selected piece unselects it.
  if (!d.moved && d.wasSelected) selected = null;
  renderBoard();
}

boardEl.addEventListener("pointerup", (e) => endDrag(e, false));
boardEl.addEventListener("pointercancel", (e) => endDrag(e, true));

// --- Buttons and dialogs --------------------------------------------------

function openColorDialog(cancellable) {
  $("color-cancel").hidden = !cancellable;
  const dialog = $("color-dialog");
  dialog.returnValue = "";
  dialog.showModal();
}

$("color-dialog").addEventListener("close", () => {
  const choice = $("color-dialog").returnValue;
  if (["white", "black", "random"].includes(choice)) {
    send({ type: "new_game", color: choice });
  } else if (!game()) {
    openColorDialog(false);
  }
});

$("color-dialog").addEventListener("cancel", (e) => {
  if (!game()) e.preventDefault();
});

$("btn-new").addEventListener("click", () => {
  const g = game();
  if (g && g.status === "playing" && !confirm("La partida en curso contará como abandono. ¿Empezar una nueva?")) return;
  openColorDialog(true);
});

$("btn-resign").addEventListener("click", () => {
  if (confirm("¿Seguro que quieres rendirte?")) send({ type: "resign" });
});

let toastTimer = null;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 4000);
}

setInterval(() => {
  if (game() && game().status === "playing") renderClocks();
}, 100);

renderBoard();
connect();
