"use strict";

const API_BASE = location.protocol === "file:" || (location.port && location.port !== "8000") ? "http://127.0.0.1:8000" : "";
const LIVE_API = "https://sportscore.com/api/widget";
const SESSION_KEY = "statstriker_session";
const CATALOG_KEY = "statstriker_team_catalog_v1";
const CATALOG_TTL = 12 * 60 * 60 * 1000;
let sessionId = localStorage.getItem(SESSION_KEY) || newSessionId();
localStorage.setItem(SESSION_KEY, sessionId);

const $ = (selector) => document.querySelector(selector);
const els = {
  messages: $("#messages"), form: $("#composer"), input: $("#input"), send: $("#btn-send"),
  chips: $("#chips"), matches: $("#matches"), menu: $("#btn-menu"), providerLabel: $("#provider-label"),
  leagueList: $("#league-list"), teamList: $("#team-list"), teamCount: $("#team-count"),
  teamsTitle: $("#teams-title"), catalogNote: $("#catalog-note"), teamSearch: $("#team-search"),
};

const LEAGUES = [
  { id: "4328", name: "Premier League", flag: "🏴", apiName: "English_Premier_League" },
  { id: "4335", name: "LaLiga", flag: "🇪🇸", apiName: "Spanish_La_Liga" },
  { id: "4332", name: "Serie A", flag: "🇮🇹", apiName: "Italian_Serie_A" },
  { id: "4331", name: "Bundesliga", flag: "🇩🇪", apiName: "German_Bundesliga" },
  { id: "4334", name: "Ligue 1", flag: "🇫🇷", apiName: "French_Ligue_1" },
];
const RULE_LABELS = {
  persona_tipster: ["🎩 Analista", ""], reglas_innegociables: ["🛡️ Reglas base", ""],
  juego_responsable: ["🆘 Juego responsable", "red"], contexto_good: ["📚 Contexto suficiente", "green"],
  contexto_low: ["📉 Contexto parcial", "yellow"], contexto_none: ["🚫 Sin datos", "red"],
  aviso_garantia: ["⚠️ Pide garantía", "yellow"], combinada: ["🔗 Combinada", ""],
  perfil_conservador: ["🐢 Conservador", "green"], perfil_moderado: ["⚖️ Moderado", ""],
  perfil_agresivo: ["🔥 Agresivo", "red"], kelly: ["🧮 Kelly", ""], mercado_1x2: ["1X2", "green"],
  mercado_doble_oportunidad: ["Doble oportunidad", "green"], mercado_over_under: ["Over/Under", "green"],
  mercado_btts: ["BTTS", "green"], mercado_handicap: ["Hándicap", "green"], mercado_corners: ["Córners", "green"],
  mercado_tarjetas: ["Tarjetas", "green"],
};
let selectedLeague = LEAGUES[0];
let catalog = {};
let latestMatches = [];
let busy = false;
let liveMatches = [];
let liveFilter = "live";
let liveRefreshTimer = null;
let selectedLiveSlug = "";
let selectedLiveDetails = null;
let liveFeedFresh = false;

function newSessionId() { return crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
function escapeHtml(value) { return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
function safeImage(url) { return typeof url === "string" && /^https:\/\//i.test(url) ? escapeHtml(url) : ""; }
async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(", ") : data.detail;
    throw new Error(detail || `Error HTTP ${response.status}`);
  }
  return data;
}

function inlineMd(text) {
  return text.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}
function renderMarkdown(markdown) {
  const lines = escapeHtml(markdown).split(/\r?\n/), output = [];
  let list = null, table = [];
  const closeList = () => { if (list) { output.push(`</${list}>`); list = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((row) => !/^\|?\s*:?-{2,}/.test(row)).map((row) => row.replace(/^\||\|$/g, "").split("|").map((cell) => inlineMd(cell.trim())));
    if (rows.length) { const [head, ...body] = rows; output.push(`<div class="table-wrap"><table><thead><tr>${head.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`); }
    table = [];
  };
  for (const source of lines) {
    const line = source.trim();
    if (line.startsWith("|")) { closeList(); table.push(line); continue; }
    flushTable();
    if (!line) { closeList(); continue; }
    let match;
    if ((match = line.match(/^#{1,6}\s+(.*)$/))) { closeList(); output.push(`<h3>${inlineMd(match[1])}</h3>`); }
    else if ((match = line.match(/^&gt;\s?(.*)$/))) { closeList(); output.push(`<blockquote>${inlineMd(match[1])}</blockquote>`); }
    else if ((match = line.match(/^[-*•]\s+(.*)$/))) { if (list !== "ul") { closeList(); output.push("<ul>"); list = "ul"; } output.push(`<li>${inlineMd(match[1])}</li>`); }
    else if ((match = line.match(/^\d+[.)]\s+(.*)$/))) { if (list !== "ol") { closeList(); output.push("<ol>"); list = "ol"; } output.push(`<li>${inlineMd(match[1])}</li>`); }
    else { closeList(); output.push(`<p>${inlineMd(line)}</p>`); }
  }
  closeList(); flushTable(); return output.join("");
}
function scrollToBottom() { els.messages.scrollTop = els.messages.scrollHeight; }
function ruleTag(rule) { const [label, color] = RULE_LABELS[rule] || [rule, ""]; return `<span class="tag ${color ? `tag--${color}` : ""}">${escapeHtml(label)}</span>`; }
function addUserMessage(text) {
  const article = document.createElement("article"); article.className = "msg msg--user";
  article.innerHTML = `<div class="msg__avatar">T</div><div class="msg__bubble"><p>${escapeHtml(text)}</p></div>`;
  els.messages.appendChild(article); scrollToBottom();
}
function addTyping() {
  const article = document.createElement("article"); article.className = "msg msg--bot";
  article.innerHTML = `<div class="msg__avatar">S</div><div class="msg__bubble"><div class="typing"><span></span><span></span><span></span></div><p class="muted">Buscando contexto y preparando el análisis…</p></div>`;
  els.messages.appendChild(article); scrollToBottom(); return article;
}
function addBotMessage({ answer, active_rules = [], sources = [] }, { isError = false } = {}) {
  const article = document.createElement("article"); article.className = `msg msg--bot${isError ? " msg--error" : ""}`;
  const rules = active_rules.filter((rule) => !["persona_tipster", "reglas_innegociables"].includes(rule));
  const sourceHtml = sources.length ? `<details><summary>Fuentes consultadas (${sources.length})</summary>${sources.map((source) => `<div class="source"><span>[${escapeHtml(source.category)}] ${escapeHtml(source.match)}</span><span class="bar" title="Similitud ${(source.similarity * 100).toFixed(0)}%"><span style="width:${(source.similarity * 100).toFixed(0)}%"></span></span></div>`).join("")}</details>` : "";
  const meta = !isError && (rules.length || sources.length) ? `<div class="msg__meta"><div class="row">${rules.map(ruleTag).join("")}</div>${sourceHtml}</div>` : "";
  article.innerHTML = `<div class="msg__avatar">${isError ? "!" : "S"}</div><div class="msg__bubble">${renderMarkdown(answer)}${meta}</div>`;
  els.messages.appendChild(article); scrollToBottom();
}

function renderLeagues() {
  $("#league-count").textContent = String(LEAGUES.length);
  els.leagueList.innerHTML = LEAGUES.map((league) => `<button class="league-button ${league.id === selectedLeague.id ? "active" : ""}" type="button" data-league="${league.id}"><span class="league-flag">${league.flag}</span><span>${escapeHtml(league.name)}</span><small>›</small></button>`).join("");
}
function renderTeams(teams) {
  const query = els.teamSearch.value.trim().toLocaleLowerCase("es");
  const filtered = teams.filter((team) => team.name.toLocaleLowerCase("es").includes(query));
  els.teamCount.textContent = String(filtered.length);
  els.catalogNote.textContent = query ? `${filtered.length} resultados en ${selectedLeague.name}` : `${teams.length} equipos · ${selectedLeague.name}`;
  els.teamList.innerHTML = filtered.length ? filtered.map((team) => {
    const badge = safeImage(team.badge);
    const logo = badge ? `<img class="team-badge" src="${badge}" alt="" data-initial="${escapeHtml(team.name.slice(0, 1).toUpperCase())}" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(team.name.slice(0, 1).toUpperCase())}</span>`;
    return `<button class="team-row" type="button" data-team="${escapeHtml(team.name)}" title="Analizar ${escapeHtml(team.name)}">${logo}<span>${escapeHtml(team.name)}</span><span class="team-region">›</span></button>`;
  }).join("") : `<p class="loading-state">No hay equipos que coincidan con la búsqueda.</p>`;
}
function getCachedCatalog(id) {
  try { const cache = JSON.parse(localStorage.getItem(CATALOG_KEY) || "{}"); return cache[id]?.expires > Date.now() && Array.isArray(cache[id].teams) ? cache[id].teams : null; } catch { return null; }
}
function saveCachedCatalog(id, teams) {
  try { const cache = JSON.parse(localStorage.getItem(CATALOG_KEY) || "{}"); cache[id] = { expires: Date.now() + CATALOG_TTL, teams }; localStorage.setItem(CATALOG_KEY, JSON.stringify(cache)); } catch { /* almacenamiento opcional */ }
}
async function loadLeague(id) {
  selectedLeague = LEAGUES.find((league) => league.id === id) || LEAGUES[0];
  renderLeagues(); els.teamsTitle.textContent = selectedLeague.name; els.teamSearch.value = "";
  const cached = catalog[id] || getCachedCatalog(id);
  if (cached) { catalog[id] = cached; renderTeams(cached); }
  else { els.teamCount.textContent = "…"; els.catalogNote.textContent = "Cargando el catálogo de la liga…"; els.teamList.innerHTML = `<div class="loading-state"><span class="loader"></span> Cargando escudos y equipos…</div>`; }
  try {
    const teams = await api(`/api/teams/${encodeURIComponent(id)}`);
    if (selectedLeague.id !== id) return;
    catalog[id] = teams; saveCachedCatalog(id, teams); renderTeams(teams);
    renderMatches(latestMatches);
  } catch (error) {
    if (selectedLeague.id !== id) return;
    if (cached) { renderTeams(cached); els.catalogNote.textContent = `${cached.length} equipos · catálogo guardado`; }
    else { els.teamCount.textContent = "0"; els.catalogNote.textContent = "No se pudo conectar con el catálogo."; els.teamList.innerHTML = `<p class="loading-state">${escapeHtml(error.message)}. Comprueba que el servidor esté conectado.</p>`; }
  }
}

function setStatus(id, state, text) { const dot = $(`#dot-${id}`), label = $(`#st-${id}`); if (dot && label) { dot.className = `dot ${state}`; label.textContent = text; } }
async function loadHealth() {
  try {
    const health = await api("/api/health");
    setStatus("api", "ok", "online");
    setStatus("llm", health.llm.ready ? (health.llm.provider === "mock" ? "warn" : "ok") : "err", health.llm.ready ? health.llm.provider : "sin API key");
    setStatus("vec", health.vector_db.documents ? "ok" : "warn", health.vector_db.documents ? `${health.vector_db.documents} docs` : "sin datos");
    els.providerLabel.textContent = health.llm.ready ? `Modelo ${health.llm.provider} · embeddings ${health.embedding_provider}` : "Analista IA sin configurar";
  } catch {
    setStatus("api", "err", "offline"); setStatus("llm", "err", "—"); setStatus("vec", "err", "—");
    els.providerLabel.textContent = "Backend desconectado · inicia FastAPI";
  }
}
function crestFor(name) {
  for (const teams of Object.values(catalog)) { const found = teams.find((team) => team.name.toLocaleLowerCase() === name.toLocaleLowerCase()); if (found?.badge) return safeImage(found.badge); }
  return "";
}
function teamSide(name) { const badge = crestFor(name); return `<div class="match-side">${badge ? `<img class="team-badge" src="${badge}" data-initial="${escapeHtml(name.slice(0, 1).toUpperCase())}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(name.slice(0, 1))}</span>`}<span>${escapeHtml(name)}</span></div>`; }
async function loadMatches() {
  try {
    const matches = await api("/api/matches");
    latestMatches = matches;
    if (!matches.length) { els.matches.innerHTML = `<p class="loading-state">No hay partidos cargados en la base de análisis.</p>`; return; }
    renderMatches(matches);
  } catch { els.matches.innerHTML = `<p class="loading-state">Partidos no disponibles.</p>`; }
}
function renderMatches(matches) {
  if (!matches.length) { els.matches.innerHTML = `<p class="loading-state">No hay partidos cargados en la base de análisis.</p>`; return; }
  els.matches.innerHTML = matches.map((match) => `<div class="match-card" tabindex="0" role="button" data-q="Analiza el ${escapeHtml(match.home_team)} vs ${escapeHtml(match.away_team)}: ¿qué mercado tiene más valor?"><div class="match-card__comp">⚽ ${escapeHtml(match.competition)}</div><div class="match-card__teams">${teamSide(match.home_team)}<span class="match-vs">vs</span>${teamSide(match.away_team)}</div><div class="match-card__date">◷ ${escapeHtml(match.date)}</div></div>`).join("");
}
async function loadHistory() {
  try {
    const history = await api(`/api/history/${encodeURIComponent(sessionId)}`);
    history.forEach((item) => { addUserMessage(item.user_message); addBotMessage({ answer: item.bot_response, active_rules: item.active_rules, sources: item.sources }); });
  } catch { /* el chat informa si la API no está disponible */ }
}
async function sendMessage(text) {
  const message = text.trim(); if (!message || busy) return;
  busy = true; els.send.disabled = true; els.input.value = ""; autoResize(); addUserMessage(message); const typing = addTyping();
  try {
    const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message, session_id: sessionId }) });
    typing.remove(); addBotMessage(data);
  } catch (error) { typing.remove(); addBotMessage({ answer: `**Error:** ${error.message}` }, { isError: true }); }
  finally { busy = false; els.send.disabled = false; els.input.focus(); }
}
function autoResize() { els.input.style.height = "auto"; els.input.style.height = `${Math.min(els.input.scrollHeight, 120)}px`; }

els.form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(els.input.value); });
els.input.addEventListener("input", autoResize);
els.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(els.input.value); } });
els.chips.addEventListener("click", (event) => { const chip = event.target.closest(".chip"); if (chip) sendMessage(chip.textContent); });
els.leagueList.addEventListener("click", (event) => { const button = event.target.closest("[data-league]"); if (button) loadLeague(button.dataset.league); });
els.teamSearch.addEventListener("input", () => renderTeams(catalog[selectedLeague.id] || []));
els.teamList.addEventListener("click", (event) => { const button = event.target.closest("[data-team]"); if (button) { els.input.value = `Analiza el próximo partido de ${button.dataset.team}`; autoResize(); els.input.focus(); $("#chat").scrollIntoView({ behavior: "smooth", block: "start" }); } });
function handleBadgeError(event) {
  const image = event.target.closest(".team-badge");
  if (!image) return;
  const fallback = document.createElement("span"); fallback.className = "team-placeholder"; fallback.textContent = image.dataset.initial || "⚽"; image.replaceWith(fallback);
}
els.teamList.addEventListener("error", handleBadgeError, true);
els.matches.addEventListener("error", handleBadgeError, true);
function useMatch(event) { const card = event.target.closest(".match-card"); if (!card) return; els.input.value = card.dataset.q; autoResize(); els.input.focus(); $("#chat").scrollIntoView({ behavior: "smooth", block: "start" }); }
els.matches.addEventListener("click", useMatch);
els.matches.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); useMatch(event); } });
els.menu.addEventListener("click", () => $("#ligas").scrollIntoView({ behavior: "smooth", block: "start" }));

function setView(view) {
  const isLive = view === "live";
  $("#home-view").hidden = isLive;
  $("#live-view").hidden = !isLive;
  document.querySelectorAll(".main-nav [data-view]").forEach((link) => link.classList.toggle("active", link.dataset.view === view));
  if (liveRefreshTimer) { clearInterval(liveRefreshTimer); liveRefreshTimer = null; }
  if (isLive) {
    loadLiveMatches();
    liveRefreshTimer = setInterval(loadLiveMatches, 60_000);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
document.querySelectorAll("[data-view]").forEach((control) => control.addEventListener("click", (event) => {
  const view = control.dataset.view;
  if (!view) return;
  event.preventDefault();
  setView(view);
}));

function liveStatus(match) {
  return `${match.status || ""} ${match.status_text || ""}`.trim().toLocaleLowerCase("en");
}
function statusIndicatesLive(match) {
  const status = liveStatus(match);
  if (/finished|full.?time|\bft\b|ended|cancelled|postponed|not started/.test(status)) return false;
  return /live|in.?play|progress|half.?time|\bht\b|extra.?time|penalt|\d{1,3}(?:\+\d+)?\s*['’]/.test(status);
}
function isLive(match) { return liveFeedFresh && statusIndicatesLive(match); }
function isFinished(match) { return /finished|full.?time|\bft\b|ended/.test(liveStatus(match)); }
function matchSlug(match) {
  if (match.slug) return String(match.slug);
  const parts = String(match.url || "").split("/").filter(Boolean);
  return parts.length >= 4 ? parts[parts.length - 2] : "";
}
function formatMatchClock(match) {
  const status = String(match.status_text || "").trim();
  if (!liveFeedFresh && statusIndicatesLive(match)) return "Datos demorados";
  if (status) return status;
  if (isLive(match)) return "EN JUEGO";
  if (isFinished(match)) return "FINAL";
  if (match.time) return new Date(match.time).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
  return "—";
}
function renderLiveMatches() {
  const filtered = liveMatches.filter((match) => liveFilter === "live" ? isLive(match) : liveFilter === "finished" ? isFinished(match) : true);
  $("#live-match-count").textContent = String(filtered.length);
  $("#live-feed-title").textContent = liveFilter === "live" ? "En directo ahora" : liveFilter === "finished" ? "Partidos finalizados" : "Todos los partidos";
  if (!filtered.length) {
    const copy = liveFilter === "live"
      ? "No se encontraron partidos en juego en este momento. Los marcadores se actualizarán automáticamente."
      : "No hay partidos para mostrar en esta categoría.";
    $("#live-matches").innerHTML = `<div class="live-empty"><span class="stat-ring">⚽</span><strong>${liveFilter === "live" ? "Sin partidos en directo" : "Sin resultados"}</strong><p>${copy}</p></div>`;
    return;
  }
  $("#live-matches").innerHTML = filtered.map((match) => {
    const slug = matchSlug(match);
    const selected = slug && slug === selectedLiveSlug;
    const clock = formatMatchClock(match);
    const live = isLive(match);
    const homeLogo = safeImage(match.home_logo), awayLogo = safeImage(match.away_logo), leagueLogo = safeImage(match.competition_logo);
    return `<article class="live-match-card ${selected ? "selected" : ""}" tabindex="0" role="button" data-live-slug="${escapeHtml(slug)}" aria-label="Ver ${escapeHtml(match.home)} contra ${escapeHtml(match.away)}"><div class="live-card-league">${leagueLogo ? `<img src="${leagueLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "⚽"}<span>${escapeHtml(match.competition || "Fútbol")}</span></div><div class="live-card-score"><div class="live-card-team">${homeLogo ? `<img src="${homeLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(String(match.home || "?").slice(0,1))}</span>`}<span>${escapeHtml(match.home || "Local")}</span></div><div class="live-score">${escapeHtml(match.home_score ?? "–")} - ${escapeHtml(match.away_score ?? "–")}<small class="live-status ${isFinished(match) ? "finished" : live ? "" : "scheduled"}">${escapeHtml(clock)}</small></div><div class="live-card-team away">${awayLogo ? `<img src="${awayLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(String(match.away || "?").slice(0,1))}</span>`}<span>${escapeHtml(match.away || "Visitante")}</span></div></div><div class="live-card-footer"><span>${live ? "● EN DIRECTO" : isFinished(match) ? "JORNADA FINALIZADA" : "PARTIDO"}</span><strong>${escapeHtml(clock)}</strong></div></article>`;
  }).join("");
}
function statLabel(name) {
  return String(name || "Estadística").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/^./, (letter) => letter.toUpperCase());
}
function detailsStats(details) {
  const raw = details.statistics || details.stats || details.match?.statistics || details.match?.stats;
  if (Array.isArray(raw)) return raw.map((item) => ({ name: item.name || item.type || item.label, home: item.home ?? item.home_value ?? item.homeValue, away: item.away ?? item.away_value ?? item.awayValue })).filter((item) => item.home != null || item.away != null).slice(0, 7);
  if (raw && typeof raw === "object") return Object.entries(raw).map(([name, values]) => ({ name, home: values?.home ?? values?.home_value, away: values?.away ?? values?.away_value })).filter((item) => item.home != null || item.away != null).slice(0, 7);
  return [];
}
function detailsTimeline(details) {
  const raw = details.timeline || details.events || details.incidents || details.match?.timeline || details.match?.events;
  if (!Array.isArray(raw)) return [];
  return raw.slice(-6).reverse().map((item) => ({ time: item.time || item.minute || item.elapsed || "–", text: item.text || item.description || item.event || item.type || "Evento del partido" }));
}
function renderLiveDetails(match, details = null) {
  if (!match) {
    $("#live-details").innerHTML = `<div class="live-empty compact"><span class="stat-ring">⚽</span><p>Elige un partido para consultar sus detalles.</p></div>`;
    return;
  }
  const homeLogo = safeImage(match.home_logo), awayLogo = safeImage(match.away_logo);
  const [homeLogoMarkup, awayLogoMarkup] = [homeLogo, awayLogo].map((logo) => logo ? `<img src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "⚽");
  const stats = details ? detailsStats(details) : [];
  const timeline = details ? detailsTimeline(details) : [];
  const statsMarkup = stats.length ? `<h3 class="detail-section-title">Estadísticas del partido</h3>${stats.map((stat) => `<div class="stat-row"><span>${escapeHtml(stat.home ?? "—")}</span><strong>${escapeHtml(statLabel(stat.name))}</strong><span>${escapeHtml(stat.away ?? "—")}</span></div>`).join("")}` : `<p class="detail-unavailable">${details ? "El proveedor aún no ofrece estadísticas para este encuentro." : "Consultando los datos disponibles del partido…"}</p>`;
  const eventsMarkup = timeline.length ? `<h3 class="detail-section-title">Últimos eventos</h3><ul class="event-list">${timeline.map((event) => `<li><time>${escapeHtml(event.time)}</time><span>${escapeHtml(event.text)}</span></li>`).join("")}</ul>` : "";
  $("#live-details").innerHTML = `<h3 class="selected-match-title">${escapeHtml(match.home)} vs ${escapeHtml(match.away)}</h3><p class="selected-match-comp">${escapeHtml(match.competition || "Fútbol")} · ${escapeHtml(formatMatchClock(match))}</p><div class="detail-score">${homeLogoMarkup}<strong>${escapeHtml(match.home_score ?? "–")} : ${escapeHtml(match.away_score ?? "–")}</strong>${awayLogoMarkup}</div><div class="detail-team-names"><span>${escapeHtml(match.home)}</span><span>${escapeHtml(match.away)}</span></div>${statsMarkup}${eventsMarkup}`;
}
async function loadLiveDetails(slug) {
  const match = liveMatches.find((item) => matchSlug(item) === slug);
  selectedLiveSlug = slug;
  selectedLiveDetails = null;
  renderLiveMatches();
  renderLiveDetails(match);
  if (!slug) return;
  try {
    const response = await fetch(`${LIVE_API}/match/?sport=football&slug=${encodeURIComponent(slug)}`, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (selectedLiveSlug === slug) { selectedLiveDetails = payload.match || payload; renderLiveDetails(match, selectedLiveDetails); }
  } catch {
    if (selectedLiveSlug === slug) { selectedLiveDetails = {}; renderLiveDetails(match, selectedLiveDetails); }
  }
}
async function loadLiveMatches() {
  const refreshButton = $("#live-refresh");
  refreshButton.classList.add("is-loading");
  try {
    const response = await fetch(`${LIVE_API}/matches/?sport=football&limit=50&src=statstriker`, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(12000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    liveMatches = Array.isArray(payload.matches) ? payload.matches : [];
    const updated = payload.updated ? new Date(payload.updated) : null;
    const fresh = updated && Date.now() - updated.getTime() < 5 * 60 * 1000;
    liveFeedFresh = !updated || (fresh && !Number.isNaN(updated.valueOf()));
    $("#live-updated").textContent = updated && !Number.isNaN(updated.valueOf())
      ? `${fresh ? "Actualizado" : "Feed demorado"}: ${updated.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}`
      : "Marcador actualizado";
    renderLiveMatches();
    if (selectedLiveSlug) {
      const selected = liveMatches.find((match) => matchSlug(match) === selectedLiveSlug);
      if (selected) renderLiveDetails(selected, selectedLiveDetails);
    }
  } catch {
    liveFeedFresh = false;
    $("#live-updated").textContent = "Fuente de marcador no disponible";
    $("#live-matches").innerHTML = `<div class="live-empty"><strong>No se pudo cargar el marcador</strong><p>Revisa tu conexión e inténtalo de nuevo. Los marcadores no se sustituyen por datos simulados.</p><button class="refresh-button" type="button" data-live-retry>Reintentar</button></div>`;
  } finally { refreshButton.classList.remove("is-loading"); }
}
$("#live-filter").addEventListener("change", (event) => { liveFilter = event.target.value; renderLiveMatches(); });
$("#live-refresh").addEventListener("click", loadLiveMatches);
$("#live-matches").addEventListener("click", (event) => { const card = event.target.closest("[data-live-slug]"); if (card) loadLiveDetails(card.dataset.liveSlug); });
$("#live-matches").addEventListener("click", (event) => { if (event.target.closest("[data-live-retry]")) loadLiveMatches(); });
$("#live-matches").addEventListener("keydown", (event) => { const card = event.target.closest("[data-live-slug]"); if (card && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); loadLiveDetails(card.dataset.liveSlug); } });
document.addEventListener("error", (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.closest(".live-view")) return;
  const fallback = document.createElement("span"); fallback.className = "team-placeholder"; fallback.textContent = "⚽"; image.replaceWith(fallback);
}, true);
document.querySelectorAll(".main-nav .nav-link:not([data-view])").forEach((link) => link.addEventListener("click", (event) => {
  if (!$("#home-view").hidden) return;
  event.preventDefault();
  const target = link.getAttribute("href");
  setView("home");
  window.setTimeout(() => document.querySelector(target)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
}));

renderLeagues();
(async () => { await loadHealth(); await Promise.all([loadLeague(selectedLeague.id), loadMatches(), loadHistory()]); })();
