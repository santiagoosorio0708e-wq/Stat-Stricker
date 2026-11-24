"use strict";

// Keep the UI connected to the active backend even if an older server is open on another port.
const API_BASE = window.location.port === "8011"
  ? window.location.origin
  : "http://127.0.0.1:8011";
const SESSION_KEY = "statstriker_session";
const CATALOG_KEY = "statstriker_team_catalog_v3";
const CATALOG_TTL = 12 * 60 * 60 * 1000;
const FIXTURE_CACHE_KEY = "statstriker_upcoming_fixtures_v3";
const FIXTURE_CACHE_TTL = 3 * 60 * 1000;
const PROFILE_STORAGE_KEY = "statstriker_profile_v1";
const AVATAR_STORAGE_KEY = "statstriker_profile_avatar_v1";
const FAVORITE_TEAM_KEY = "statstriker_favorite_teams_v1";
const CONVERSATIONS_KEY = "statstriker_conversations_v1";
const PREFERENCES_ENABLED_KEY = "statstriker_preferences_enabled_v1";
const FEATURED_LEAGUE_IDS = ["39", "140", "78", "135", "61", "2", "3", "13", "71", "253", "143"];
let conversations = loadConversations();
let sessionId = localStorage.getItem(SESSION_KEY) || conversations[0]?.id || newSessionId();
localStorage.setItem(SESSION_KEY, sessionId);
if (!conversations.some((conversation) => conversation.id === sessionId)) conversations.unshift({ id: sessionId, title: "Conversación anterior", createdAt: Date.now(), updatedAt: Date.now(), matchContext: null });

const $ = (selector) => document.querySelector(selector);
const els = {
  messages: $("#messages"), form: $("#composer"), input: $("#input"), send: $("#btn-send"),
  chips: $("#chips"), matches: $("#matches"), menu: $("#btn-menu"), providerLabel: $("#provider-label"),
  leagueList: $("#league-list"), teamList: $("#team-list"), teamCount: $("#team-count"),
  teamsTitle: $("#teams-title"), catalogNote: $("#catalog-note"), teamSearch: $("#team-search"),
};

let LEAGUES = [
  { id: "39", name: "Premier League", country: "England", season: 2026, logo: "https://media.api-sports.io/football/leagues/39.png" },
  { id: "140", name: "LaLiga", country: "Spain", season: 2026, logo: "https://media.api-sports.io/football/leagues/140.png" },
  { id: "78", name: "Bundesliga", country: "Germany", season: 2026, logo: "https://media.api-sports.io/football/leagues/78.png" },
  { id: "135", name: "Serie A", country: "Italy", season: 2026, logo: "https://media.api-sports.io/football/leagues/135.png" },
  { id: "61", name: "Ligue 1", country: "France", season: 2026, logo: "https://media.api-sports.io/football/leagues/61.png" },
  { id: "2", name: "UEFA Champions League", country: "World", season: 2026, logo: "https://media.api-sports.io/football/leagues/2.png" },
  { id: "3", name: "UEFA Europa League", country: "World", season: 2026, logo: "https://media.api-sports.io/football/leagues/3.png" },
  { id: "13", name: "Copa Libertadores", country: "World", season: 2026, logo: "https://media.api-sports.io/football/leagues/13.png" },
  { id: "71", name: "Brasileir\u00e3o S\u00e9rie A", country: "Brazil", season: 2026, logo: "https://media.api-sports.io/football/leagues/71.png" },
  { id: "253", name: "MLS", country: "USA", season: 2026, logo: "https://media.api-sports.io/football/leagues/253.png" },
  { id: "143", name: "Copa del Rey", country: "Spain", season: 2026, logo: "https://media.api-sports.io/football/leagues/143.png" },
];
const COUNTRY_LABELS = {
  England: "Inglaterra", Spain: "España", Germany: "Alemania", Italy: "Italia",
  France: "Francia", World: "Competiciones internacionales", Brazil: "Brasil", USA: "Estados Unidos",
  Scotland: "Escocia", Wales: "Gales",
};
function countryLabel(country) {
  const key = String(country || "").trim();
  return COUNTRY_LABELS[key] || key;
}
function buildAllCountries() {
  const base = [
    { id: "World", name: "Competiciones internacionales", flag: "" },
    { id: "England", name: "Inglaterra", flag: "https://media.api-sports.io/flags/gb.svg" },
    { id: "Scotland", name: "Escocia", flag: "https://flagcdn.com/w40/gb-sct.png" },
    { id: "Wales", name: "Gales", flag: "https://flagcdn.com/w40/gb-wls.png" },
    { id: "Spain", name: "España", flag: "https://media.api-sports.io/flags/es.svg" },
    { id: "Germany", name: "Alemania", flag: "https://media.api-sports.io/flags/de.svg" },
    { id: "Italy", name: "Italia", flag: "https://media.api-sports.io/flags/it.svg" },
    { id: "France", name: "Francia", flag: "https://media.api-sports.io/flags/fr.svg" },
    { id: "Brazil", name: "Brasil", flag: "https://media.api-sports.io/flags/br.svg" },
    { id: "USA", name: "Estados Unidos", flag: "https://media.api-sports.io/flags/us.svg" },
  ];
  const alreadyCoveredIso = new Set(["ES", "DE", "IT", "FR", "BR", "US"]);
  const isoCodes = (
    "AF AL DZ AD AO AG SA AR AM AU AT AZ BS BH BD BB BE BZ BJ BY BO BA BW BG BF BI BT CV KH CM CA QA TD CL CN CY CO KM CG CD KP KR CR CI HR CU DK DM EC EG SV AE ER SK SI EE ET PH FI FJ GA GM GE GH GD GR GT GN GQ GW GY HT HN HU IN ID IQ IR IE IS IL JM JP JO KZ KE KG KI KW LA LS LV LB LR LY LI LT LU MK MG MY MW MV ML MT MA MU MR MX FM MD MC MN ME MZ MM NA NR NP NI NE NG NO NZ OM NL PK PW PA PG PY PE PL PT GB CF CZ DO RW RO RU WS KN SM VC LC ST SN RS SC SL SG SY SO LK ZA SD SS SE CH SR TH TZ TJ TL TG TO TT TN TM TR TV UA UG UY UZ VU VE VN YE DJ ZM ZW"
  ).split(" ");
  let regionNames = null;
  try { regionNames = new Intl.DisplayNames(["es"], { type: "region" }); } catch { /* respaldo */ }
  const extra = isoCodes
    .filter((code) => !alreadyCoveredIso.has(code))
    .map((code) => ({
      id: code,
      name: (regionNames && regionNames.of(code)) || code,
      flag: `https://flagcdn.com/w40/${code.toLowerCase()}.png`,
    }));
  const international = base[0];
  const rest = [...base.slice(1), ...extra].sort((a, b) => a.name.localeCompare(b.name, "es"));
  return [international, ...rest];
}
let COUNTRIES = buildAllCountries();
const RULE_LABELS = {
  persona_tipster: ["🎩 Analista", ""], reglas_innegociables: ["🛡️ Reglas base", ""],
  juego_responsable: ["🆘 Juego responsable", "red"], contexto_good: ["📚 Contexto suficiente", "green"],
  contexto_low: ["📉 Contexto parcial", "yellow"], contexto_none: ["🚫 Sin datos", "red"],
  aviso_garantia: ["⚠️ Pide garantía", "yellow"], combinada: ["🔗 Combinada", ""],
  perfil_conservador: ["🐢 Conservador", "green"], perfil_moderado: ["⚖️ Moderado", ""],
  perfil_agresivo: ["🔥 Agresivo", "red"], kelly: ["🧮 Kelly", ""], mercado_1x2: ["1X2", "green"],
  mercado_doble_oportunidad: ["Doble oportunidad", "green"], mercado_over_under: ["Over/Under", "green"],
  mercado_btts: ["BTTS", "green"], mercado_handicap: ["Hándicap", "green"], mercado_corners: ["Córners", "green"],
  mercado_tarjetas: ["Tarjetas", "green"], ultimos_5_partidos: ["📊 Últimos 5P", "green"], estadisticas_jugador: ["🏃 Jugador", "green"], valor_cuota_objetiva: ["💎 Cuota objetiva", "yellow"], analisis_foto_apuesta: ["📸 Foto de apuesta", "yellow"],
};
let selectedLeague = LEAGUES[0];
let catalog = {};
const pendingChats = new Set();
let liveMatches = [];
let liveFilter = "live";
let liveRefreshTimer = null;
let selectedLiveSlug = "";
let selectedLiveDetails = null;
let liveFeedFresh = false;
let upcomingFixtures = [];
let selectedFixtureDate = /^\d{4}-\d{2}-\d{2}$/.test(localStorage.getItem("statstriker_selected_fixture_date") || "")
  ? localStorage.getItem("statstriker_selected_fixture_date") : bogotaDate();
let upcomingRequestId = 0;
let lastFixtureContext = null;
let upcomingTimer = null;
let quickAnalysisState = { key: "", loading: false, error: "", suggestions: [] };
let favoriteLeagueIds = loadFavoriteLeagues();
let favoriteTeams = loadFavoriteTeams();
let recommendedTeamGroups = [];
let agendaRequest = 0;
let agendaFixtures = [];
let analyticsData = null;
let selectedAnalyticsMatch = "";
let comparisonLeagueTeams = [];
let comparisonRequestId = 0;

function newSessionId() { return crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
function loadConversations() {
  try { const value = JSON.parse(localStorage.getItem(CONVERSATIONS_KEY) || "[]"); return Array.isArray(value) ? value.filter((item) => item?.id) : []; }
  catch { return []; }
}
function saveConversations() { localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations)); }
function activeConversation() { return conversations.find((item) => item.id === sessionId); }
function restoreFixtureContext(context) {
  if (!context) return null;
  return { ...context, time: parseFixtureTime(context.time), homeLogo: context.homeLogo || context.home_logo || "", awayLogo: context.awayLogo || context.away_logo || "" };
}
function renderConversations() {
  const picker = $("#conversation-picker");
  if (!picker) return;
  picker.innerHTML = conversations.slice().sort((a, b) => b.updatedAt - a.updatedAt).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.title || "Nueva conversación")}</option>`).join("");
  picker.value = sessionId;
}
function setConversationTitle(message) {
  const conversation = activeConversation();
  if (!conversation || conversation.title !== "Conversación anterior" && conversation.title !== "Nueva conversación") return;
  conversation.title = message.replace(/\s+/g, " ").trim().slice(0, 42) || "Nueva conversación";
  conversation.updatedAt = Date.now(); saveConversations(); renderConversations();
}
function escapeHtml(value) { return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
function safeImage(url) { return typeof url === "string" && /^https:\/\//i.test(url) ? escapeHtml(url) : ""; }
function safeTurnImageUrl(item) {
  if (typeof item?.imageUrl === "string" && /^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$/i.test(item.imageUrl)) return item.imageUrl;
  const data = String(item?.user_image_data || "").trim();
  const mime = String(item?.user_image_mime || "image/jpeg").trim();
  if (data && /^image\/(png|jpeg|webp|gif)$/i.test(mime) && /^[A-Za-z0-9+/=]+$/.test(data)) {
    return `data:${mime};base64,${data}`;
  }
  return "";
}
const CHAT_DB_NAME = "StatStrikerChatDB";
const CHAT_STORE_NAME = "sessions";
const LOCAL_TURNS_FALLBACK_KEY = "statstriker_local_turns_v1";
let chatDbPromise = null;
function openChatDb() {
  if (!("indexedDB" in window)) return Promise.resolve(null);
  if (chatDbPromise) return chatDbPromise;
  chatDbPromise = new Promise((resolve) => {
    try {
      const req = indexedDB.open(CHAT_DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(CHAT_STORE_NAME)) db.createObjectStore(CHAT_STORE_NAME, { keyPath: "sessionId" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch { resolve(null); }
  });
  return chatDbPromise;
}
function readFallbackTurnsMap() {
  try { const parsed = JSON.parse(localStorage.getItem(LOCAL_TURNS_FALLBACK_KEY) || "{}"); return parsed && typeof parsed === "object" ? parsed : {}; }
  catch { return {}; }
}
function writeFallbackTurnsMap(map) {
  try { localStorage.setItem(LOCAL_TURNS_FALLBACK_KEY, JSON.stringify(map)); } catch {
    try {
      const compact = {};
      Object.entries(map).slice(-8).forEach(([sid, turns]) => {
        compact[sid] = (Array.isArray(turns) ? turns : []).slice(-12).map((t) => ({ ...t, user_image_data: "", imageUrl: "" }));
      });
      localStorage.setItem(LOCAL_TURNS_FALLBACK_KEY, JSON.stringify(compact));
    } catch { /* sin espacio en localStorage */ }
  }
}
async function readLocalTurns(targetSessionId) {
  const db = await openChatDb();
  if (db) {
    const idbTurns = await new Promise((resolve) => {
      try {
        const tx = db.transaction(CHAT_STORE_NAME, "readonly");
        const req = tx.objectStore(CHAT_STORE_NAME).get(targetSessionId);
        req.onsuccess = () => resolve(Array.isArray(req.result?.turns) ? req.result.turns : null);
        req.onerror = () => resolve(null);
      } catch { resolve(null); }
    });
    if (idbTurns && idbTurns.length) return idbTurns;
  }
  const map = readFallbackTurnsMap();
  return Array.isArray(map[targetSessionId]) ? map[targetSessionId] : [];
}
async function writeLocalTurns(targetSessionId, turns) {
  const cleanTurns = (Array.isArray(turns) ? turns : []).slice(-60);
  const db = await openChatDb();
  if (db) {
    await new Promise((resolve) => {
      try {
        const tx = db.transaction(CHAT_STORE_NAME, "readwrite");
        tx.objectStore(CHAT_STORE_NAME).put({ sessionId: targetSessionId, turns: cleanTurns, updatedAt: Date.now() });
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch { resolve(); }
    });
  }
  const map = readFallbackTurnsMap();
  map[targetSessionId] = cleanTurns;
  writeFallbackTurnsMap(map);
}
async function deleteLocalTurns(targetSessionId) {
  const db = await openChatDb();
  if (db) {
    await new Promise((resolve) => {
      try {
        const tx = db.transaction(CHAT_STORE_NAME, "readwrite");
        tx.objectStore(CHAT_STORE_NAME).delete(targetSessionId);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch { resolve(); }
    });
  }
  const map = readFallbackTurnsMap();
  delete map[targetSessionId];
  writeFallbackTurnsMap(map);
}
function openImageLightbox(src) {
  if (!src) return;
  let modal = $("#image-lightbox");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "image-lightbox";
    modal.className = "image-lightbox";
    modal.innerHTML = `<button class="image-lightbox__close" type="button" aria-label="Cerrar imagen">×</button><img class="image-lightbox__img" alt="Captura de apuesta guardada">`;
    modal.addEventListener("click", (event) => {
      if (event.target === modal || event.target.closest(".image-lightbox__close")) modal.hidden = true;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) modal.hidden = true;
    });
    document.body.appendChild(modal);
  }
  modal.querySelector(".image-lightbox__img").src = src;
  modal.hidden = false;
}
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
function addUserMessage(text, imageUrl = "") {
  const article = document.createElement("article"); article.className = "msg msg--user";
  const imgHtml = imageUrl ? `<img class="msg__image" src="${escapeHtml(imageUrl)}" alt="Foto de apuesta adjunta">` : "";
  const textHtml = text ? `<p>${escapeHtml(text)}</p>` : "";
  article.innerHTML = `<div class="msg__avatar">T</div><div class="msg__bubble">${imgHtml}${textHtml}</div>`;
  els.messages.appendChild(article); scrollToBottom();
}
function addTyping() {
  const article = document.createElement("article"); article.className = "msg msg--bot";
  article.innerHTML = `<div class="msg__avatar">S</div><div class="msg__bubble"><div class="typing"><span></span><span></span><span></span></div><p class="muted">Buscando contexto y preparando el análisis…</p></div>`;
  els.messages.appendChild(article); scrollToBottom(); return article;
}
function addBotMessage({ answer, active_rules = [], sources = [] }, { isError = false, fixture = null, retryMessage = "" } = {}) {
  const article = document.createElement("article"); article.className = `msg msg--bot${isError ? " msg--error" : ""}`;
  const rules = active_rules.filter((rule) => !["persona_tipster", "reglas_innegociables"].includes(rule));
  const sourceHtml = sources.length ? `<details><summary>Fuentes consultadas (${sources.length})</summary>${sources.map((source) => `<div class="source"><span>[${escapeHtml(source.category)}] ${escapeHtml(source.match)}</span><span class="bar" title="Similitud ${(source.similarity * 100).toFixed(0)}%"><span style="width:${(source.similarity * 100).toFixed(0)}%"></span></span></div>`).join("")}</details>` : "";
  const meta = !isError && (rules.length || sources.length) ? `<div class="msg__meta"><div class="row">${rules.map(ruleTag).join("")}</div>${sourceHtml}</div>` : "";
  const fixtureCard = fixture ? renderChatFixtureCard(fixture) : "";
  const retry = isError && retryMessage ? `<button class="chat-retry-button" type="button" data-retry-message="${escapeHtml(retryMessage)}">Reintentar solicitud</button>` : "";
  article.innerHTML = `<div class="msg__avatar">${isError ? "!" : "S"}</div><div class="msg__bubble">${renderMarkdown(answer)}${fixtureCard}${meta}${retry}</div>`;
  els.messages.appendChild(article); scrollToBottom();
}

function renderChatFixtureCard(fixture) {
  const homeLogo = safeImage(fixture.homeLogo), awayLogo = safeImage(fixture.awayLogo);
  const kickoff = fixture.time && !Number.isNaN(fixture.time.valueOf())
    ? new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(fixture.time)
    : "Fecha y hora por confirmar";
  return `<section class="chat-fixture-card"><p class="chat-fixture-competition">${escapeHtml(fixture.competition)}</p><div class="chat-fixture-teams">${homeLogo ? `<img src="${homeLogo}" alt="Escudo de ${escapeHtml(fixture.home)}" loading="lazy">` : `<span class="team-placeholder">${escapeHtml(fixture.home.slice(0, 1))}</span>`}<strong>${escapeHtml(fixture.home)} <span>vs</span> ${escapeHtml(fixture.away)}</strong>${awayLogo ? `<img src="${awayLogo}" alt="Escudo de ${escapeHtml(fixture.away)}" loading="lazy">` : `<span class="team-placeholder">${escapeHtml(fixture.away.slice(0, 1))}</span>`}</div><p class="chat-fixture-kickoff">◷ ${escapeHtml(kickoff)} · hora de Colombia</p></section>`;
}

function renderLeagues() {
  const query = $("#league-search")?.value.trim().toLocaleLowerCase("es") || "";
  const filtered = LEAGUES.filter((league) => league.id !== "143" && `${league.name} ${league.country || ""}`.toLocaleLowerCase("es").includes(query));
  $("#league-count").textContent = String(filtered.length);
  els.leagueList.innerHTML = filtered.map((league) => {
    const image = safeImage(league.logo || league.country_flag);
    const icon = image ? `<img src="${image}" alt="" loading="lazy" referrerpolicy="no-referrer">` : escapeHtml(league.flag || "⚽");
    return `<button class="league-button ${league.id === selectedLeague.id ? "active" : ""}" type="button" data-league="${escapeHtml(league.id)}"><span class="league-flag">${icon}</span><span class="league-button-copy"><strong>${escapeHtml(league.name)}</strong><small>${escapeHtml(countryLabel(league.country))}</small></span></button>`;
  }).join("") || `<p class="loading-state">No se encontraron ligas.</p>`;
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
  try { const cache = JSON.parse(localStorage.getItem(CATALOG_KEY) || "{}"); return cache[id]?.expires > Date.now() && Array.isArray(cache[id].teams) && cache[id].teams.length ? cache[id].teams : null; } catch { return null; }
}
function saveCachedCatalog(id, teams) {
  if (!Array.isArray(teams) || !teams.length) return;
  try { const cache = JSON.parse(localStorage.getItem(CATALOG_KEY) || "{}"); cache[id] = { expires: Date.now() + CATALOG_TTL, teams }; localStorage.setItem(CATALOG_KEY, JSON.stringify(cache)); } catch { /* almacenamiento opcional */ }
}
async function loadLeague(id) {
  selectedLeague = LEAGUES.find((league) => league.id === id) || LEAGUES[0];
  loadRecommendedTeams(favoriteLeagueIds.includes(selectedLeague.id) ? favoriteLeagueIds : [selectedLeague.id]);
  renderLeagues(); els.teamsTitle.textContent = selectedLeague.name; els.teamSearch.value = "";
  const cached = (catalog[id]?.length ? catalog[id] : null) || getCachedCatalog(id);
  if (cached) { catalog[id] = cached; renderTeams(cached); }
  else { els.teamCount.textContent = "…"; els.catalogNote.textContent = "Cargando el catálogo de la liga…"; els.teamList.innerHTML = `<div class="loading-state"><span class="loader"></span> Cargando escudos y equipos…</div>`; }
  try {
    const league = LEAGUES.find((item) => item.id === id);
    const data = league?.season
      ? await api(`/api/football/teams?league=${encodeURIComponent(id)}&season=${encodeURIComponent(league.season)}`)
      : await api(`/api/teams/${encodeURIComponent(id)}`);
    const teams = data.teams || data;
    if (selectedLeague.id !== id) return;
    catalog[id] = teams; saveCachedCatalog(id, teams); renderTeams(teams);
  } catch (error) {
    if (selectedLeague.id !== id) return;
    if (cached) { renderTeams(cached); els.catalogNote.textContent = `${cached.length} equipos · catálogo guardado`; }
    else { els.teamCount.textContent = "0"; els.catalogNote.textContent = "No se pudo conectar con el catálogo."; els.teamList.innerHTML = `<p class="loading-state">${escapeHtml(error.message)}. Comprueba que el servidor esté conectado.</p>`; }
  }
}

async function loadFootballLeagues() {
  const cacheKey = "statstriker_api_football_leagues_v2";
  let leagues = [];
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
    if (cached?.expires > Date.now() && Array.isArray(cached.leagues)) leagues = cached.leagues;
  } catch { /* caché opcional */ }
  try {
    if (!leagues.length) {
      const data = await api("/api/football/leagues");
      leagues = Array.isArray(data.leagues) ? data.leagues : [];
      if (leagues.length) localStorage.setItem(cacheKey, JSON.stringify({ expires: Date.now() + 24 * 60 * 60 * 1000, leagues }));
    }
    leagues = leagues.filter((league) => FEATURED_LEAGUE_IDS.includes(String(league.id)));
    if (!leagues.length) return;
    const legacyIds = { "4328": "39", "4335": "140", "4332": "135", "4331": "78", "4334": "61" };
    const selectedId = legacyIds[selectedLeague.id] || selectedLeague.id;
    favoriteLeagueIds = [...new Set(favoriteLeagueIds.map((id) => legacyIds[id] || id))].filter((id) => FEATURED_LEAGUE_IDS.includes(id));
    LEAGUES = leagues.map((league) => ({ ...league, id: String(league.id), flag: "", apiName: league.name }));
    if (!LEAGUES.some((league) => league.id === "143")) LEAGUES.push({ id: "143", name: "Copa del Rey", country: "Spain", season: 2026, logo: "https://media.api-sports.io/football/leagues/143.png", flag: "" });
    if (!favoriteLeagueIds.length) favoriteLeagueIds = ["39", "140"];
    const existingIds = new Set(COUNTRIES.map((country) => country.id));
    LEAGUES.forEach((league) => {
      if (league.country && !existingIds.has(league.country)) {
        existingIds.add(league.country);
        COUNTRIES.push({ id: league.country, name: countryLabel(league.country), flag: league.country_flag || "" });
      }
    });
    const [intl, ...restCountries] = COUNTRIES;
    COUNTRIES = [intl, ...restCountries.sort((a, b) => a.name.localeCompare(b.name, "es"))];
    selectedLeague = LEAGUES.find((league) => league.id === selectedId) || LEAGUES.find((league) => favoriteLeagueIds.includes(league.id)) || LEAGUES[0];
    saveFavoriteLeagues();
    renderLeagues(); renderFavoriteLeagues(); renderProfileChoices();
    if (!$("#profile-view").hidden) renderProfile();
    await loadLeague(selectedLeague.id);
    await loadRecommendedTeams(favoriteLeagueIds);
    await initTeamComparison();
  } catch (error) {
    console.warn("No se pudo cargar el catálogo ampliado de ligas:", error.message);
  }
}

function setStatus(id, state, text) { const dot = $(`#dot-${id}`), label = $(`#st-${id}`); if (dot && label) { dot.className = `dot ${state}`; label.textContent = text; } }
async function loadHealth() {
  try {
    const health = await api("/api/health");
    setStatus("api", "ok", "online");
    $("#topbar-api-dot")?.classList.remove("is-offline");
    $("#topbar-api-dot")?.classList.add("is-online");
    if ($("#topbar-api-label")) $("#topbar-api-label").textContent = "API online";
    setStatus("llm", health.llm.ready ? (health.llm.provider === "mock" ? "warn" : "ok") : "err", health.llm.ready ? health.llm.provider : "sin API key");
    setStatus("vec", health.vector_db.documents ? "ok" : "warn", health.vector_db.documents ? `${health.vector_db.documents} docs` : "sin datos");
    const historyStatus = $("#st-history");
    if (historyStatus) historyStatus.textContent = health.history_storage?.persistent ? "SQLite local" : "No disponible";
    els.providerLabel.textContent = health.llm.ready ? `Modelo ${health.llm.provider} · embeddings ${health.embedding_provider}` : "Analista IA sin configurar";
  } catch {
    setStatus("api", "err", "offline"); setStatus("llm", "err", "—"); setStatus("vec", "err", "—");
    $("#topbar-api-dot")?.classList.remove("is-online");
    $("#topbar-api-dot")?.classList.add("is-offline");
    if ($("#topbar-api-label")) $("#topbar-api-label").textContent = "API sin conexión";
    els.providerLabel.textContent = "Backend desconectado · inicia FastAPI";
  }
}
function crestFor(name) {
  for (const teams of Object.values(catalog)) { const found = teams.find((team) => team.name.toLocaleLowerCase() === name.toLocaleLowerCase()); if (found?.badge) return safeImage(found.badge); }
  return "";
}
function teamSide(name) { const badge = crestFor(name); return `<div class="match-side">${badge ? `<img class="team-badge" src="${badge}" data-initial="${escapeHtml(name.slice(0, 1).toUpperCase())}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(name.slice(0, 1))}</span>`}<span>${escapeHtml(name)}</span></div>`; }
async function loadMatches() {
  const token = ++agendaRequest;
  agendaFixtures = [];
  els.matches.innerHTML = `<p class="loading-state"><span class="loader"></span> Buscando los encuentros más cercanos…</p>`;
  const recommendedTeams = [0, 1, 2].flatMap((rank) => recommendedTeamGroups.flatMap(({ league, teams }) => {
    const team = teams?.[rank];
    return team ? [{
      id: String(team.team_id || team.id || ""),
      name: team.name,
      badge: team.logo || team.badge || "",
      leagueId: String(league.id),
      leagueName: league.name,
      season: league.season,
    }] : [];
  }));
  const agendaTeams = favoriteTeams.length ? favoriteTeams : recommendedTeams;
  const selectedTeams = agendaTeams.filter((team) => team.id && team.season).slice(0, 10);
  if (!selectedTeams.length) {
    agendaFixtures = [];
    els.matches.innerHTML = `<p class="loading-state">Selecciona una liga favorita para ver sus próximos partidos.</p>`;
    return;
  }
  try {
    const schedules = await Promise.all(selectedTeams.map(async (team) => {
      try {
        const data = await api(`/api/football/team-fixtures?team_id=${encodeURIComponent(team.id)}&season=${encodeURIComponent(team.season)}&limit=5`, { signal: AbortSignal.timeout(15000) });
        return (data.matches || []).map((fixture) => ({ ...normalizeFixture(fixture), preferredTeam: team.name }));
      } catch { return []; }
    }));
    if (token !== agendaRequest) return;
    const officialFallback = verifiedLaLigaFallbackFixtures().filter((fixture) =>
      selectedTeams.some((team) => [fixture.homeTeamId, fixture.awayTeamId].includes(String(team.id)))
    );
    const apiFixtures = schedules.flat();
    const currentFixtures = [
      ...apiFixtures.filter((fixture) => !officialFallback.some((official) =>
        [fixture.homeTeamId, fixture.awayTeamId].includes(official.homeTeamId)
        && [fixture.homeTeamId, fixture.awayTeamId].includes(official.awayTeamId)
      )),
      ...officialFallback,
    ];
    const now = Date.now(), unique = new Map();
    currentFixtures.forEach((fixture) => {
      if (!fixture.time || Number.isNaN(fixture.time.valueOf()) || fixture.time.valueOf() < now) return;
      const key = fixture.id || `${fixture.home}|${fixture.away}|${fixture.time.toISOString()}`;
      if (!unique.has(key)) unique.set(key, fixture);
    });
    agendaFixtures = [...unique.values()].sort((a, b) => a.time - b.time).slice(0, 3);
    renderMatches(agendaFixtures);
  } catch {
    if (token === agendaRequest) agendaFixtures = [];
    if (token === agendaRequest) els.matches.innerHTML = `<p class="loading-state">No se pudo cargar la agenda. Intenta actualizar más tarde.</p>`;
  }
}
function verifiedLaLigaFallbackFixtures() {
  const fixtures = [
    { id: "rm-celta-20261121", home: "Real Madrid", away: "Celta Vigo", home_id: "133738", away_id: "133937", home_logo: "https://r2.thesportsdb.com/images/media/team/badge/vwvwrw1473502969.png", away_logo: "https://r2.thesportsdb.com/images/media/team/badge/xfjtku1690436219.png", competition: "LaLiga", competition_id: "140", competition_logo: "https://r2.thesportsdb.com/images/media/league/badge/ja4it51687628717.png", round: "13", time: "2026-11-21T15:00:00-05:00", status: "NS" },
    { id: "barca-villarreal-20261122", home: "Barcelona", away: "Villarreal", home_id: "133739", away_id: "133740", home_logo: "https://r2.thesportsdb.com/images/media/team/badge/wq9sir1639406443.png", away_logo: "https://r2.thesportsdb.com/images/media/team/badge/vrypqy1473503073.png", competition: "LaLiga", competition_id: "140", competition_logo: "https://r2.thesportsdb.com/images/media/league/badge/ja4it51687628717.png", round: "13", time: "2026-11-22T08:00:00-05:00", status: "NS" },
    { id: "getafe-atleti-20261122", home: "Getafe", away: "Atlético Madrid", home_id: "133731", away_id: "133729", home_logo: "https://r2.thesportsdb.com/images/media/team/badge/eyh2891655594452.png", away_logo: "https://r2.thesportsdb.com/images/media/team/badge/0ulh3q1719984315.png", competition: "LaLiga", competition_id: "140", competition_logo: "https://r2.thesportsdb.com/images/media/league/badge/ja4it51687628717.png", round: "13", time: "2026-11-22T15:00:00-05:00", status: "NS" },
  ].map(normalizeFixture);
  return fixtures.filter((fixture) => fixture.time && fixture.time.valueOf() >= Date.now());
}
function renderMatches(matches) {
  if (!matches.length) { els.matches.innerHTML = `<p class="loading-state">No encontramos próximos partidos de tus equipos preferidos.</p>`; return; }
  els.matches.innerHTML = matches.map((match) => {
    const leagueLogo = match.competitionLogo ? `<img src="${match.competitionLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "⚽";
    const homeLogo = match.homeLogo ? `<img src="${match.homeLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(match.home.slice(0, 1))}</span>`;
    const awayLogo = match.awayLogo ? `<img src="${match.awayLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(match.away.slice(0, 1))}</span>`;
    const round = match.round ? ` · Jornada ${String(match.round).replace(/^regular season\s*-\s*/i, "")}` : "";
    const preciseDate = fixtureLongDate(match);
    const prompt = `Analiza el partido ${match.home} vs ${match.away} de ${match.competition}. Fecha y hora: ${preciseDate} (hora de Colombia).`;
    return `<button class="match-card" type="button" data-fixture-id="${escapeHtml(match.id)}" data-q="${escapeHtml(prompt)}"><span class="match-card__comp">${leagueLogo}<span>${escapeHtml(match.competition)}${escapeHtml(round)}</span></span><span class="match-card__teams"><span class="match-side">${homeLogo}<span>${escapeHtml(match.home)}</span></span><span class="match-vs">vs</span><span class="match-side">${awayLogo}<span>${escapeHtml(match.away)}</span></span></span><span class="match-card__date">◷ ${escapeHtml(preciseDate)} · hora de Colombia</span></button>`;
  }).join("");
}
function renderTurnsList(turns) {
  els.messages.innerHTML = "";
  if (!turns || !turns.length) { renderWelcomeMessage(); return; }
  turns.forEach((item) => {
    const imgUrl = safeTurnImageUrl(item);
    addUserMessage(item.user_message, imgUrl);
    if (item.bot_response) {
      addBotMessage(
        { answer: item.bot_response, active_rules: item.active_rules || [], sources: item.sources || [] },
        { isError: Boolean(item.isError), fixture: item.fixture ? restoreFixtureContext(item.fixture) : null },
      );
    }
  });
}
async function syncBackendSessions() {
  try {
    const remoteSessions = await api("/api/history?limit=50");
    if (!Array.isArray(remoteSessions) || !remoteSessions.length) return;
    let changed = false;
    remoteSessions.forEach((remote) => {
      if (!remote?.id) return;
      const exists = conversations.some((item) => item.id === remote.id);
      if (!exists) {
        const ts = Date.parse(remote.updated_at || remote.created_at || "") || Date.now();
        conversations.push({
          id: remote.id,
          title: remote.title || "Conversación anterior",
          createdAt: Date.parse(remote.created_at || "") || ts,
          updatedAt: ts,
          matchContext: null,
        });
        changed = true;
      }
    });
    if (changed) { saveConversations(); renderConversations(); }
  } catch { /* si la API está apagada mantenemos las conversaciones locales */ }
}
async function loadHistory() {
  const activeId = sessionId;
  const localTurns = await readLocalTurns(activeId);
  if (sessionId !== activeId) return;
  if (localTurns.length) renderTurnsList(localTurns);
  try {
    const history = await api(`/api/history/${encodeURIComponent(activeId)}`);
    if (sessionId !== activeId) return;
    if (Array.isArray(history) && history.length) {
      const localById = new Map(localTurns.filter((t) => t.id != null).map((t) => [String(t.id), t]));
      const merged = history.map((item) => {
        const localMatch = localById.get(String(item.id));
        const imgUrl = safeTurnImageUrl(item) || safeTurnImageUrl(localMatch);
        return {
          ...item,
          imageUrl: imgUrl,
          fixture: localMatch?.fixture || null,
        };
      });
      const maxRemoteId = Math.max(0, ...history.map((h) => Number(h.id) || 0));
      const localOnly = localTurns.filter((t) => !t.id && (!t.syncedBeforeId || t.syncedBeforeId >= maxRemoteId));
      const combined = [...merged, ...localOnly];
      await writeLocalTurns(activeId, combined);
      if (sessionId === activeId) renderTurnsList(combined);
    } else if (!localTurns.length) {
      renderWelcomeMessage();
    }
  } catch {
    if (sessionId === activeId && !localTurns.length) renderWelcomeMessage();
  }
}
function renderWelcomeMessage() {
  els.messages.innerHTML = `<article class="msg msg--bot"><div class="msg__avatar">S</div><div class="msg__bubble"><p>¡Hola! Soy <strong>StatStriker</strong>, tu analista de datos deportivos.</p><p>Cuéntame tu propuesta de apuesta y la evaluaré con estadísticas, enfrentamientos, contexto y riesgo.</p></div></article>`;
}
function switchConversation(id) {
  if (!conversations.some((item) => item.id === id) || id === sessionId) return;
  sessionId = id; localStorage.setItem(SESSION_KEY, sessionId);
  lastFixtureContext = restoreFixtureContext(activeConversation()?.matchContext);
  els.send.disabled = pendingChats.has(sessionId);
  renderConversations(); loadHistory();
}
function createConversation() {
  const id = newSessionId();
  conversations.push({ id, title: "Nueva conversación", createdAt: Date.now(), updatedAt: Date.now(), matchContext: null });
  saveConversations(); sessionId = id; localStorage.setItem(SESSION_KEY, id);
  lastFixtureContext = null; els.send.disabled = false; renderConversations(); renderWelcomeMessage(); els.input.value = ""; autoResize(); els.input.focus();
}
async function deleteCurrentConversation() {
  const current = activeConversation();
  const title = current?.title || "esta conversación";
  if (!confirm(`¿Terminar y eliminar "${title}"?`)) return;
  const targetId = sessionId;
  pendingChats.delete(targetId);
  try { await api(`/api/history/${encodeURIComponent(targetId)}`, { method: "DELETE" }); } catch { /* si no existe en BD, continuamos */ }
  await deleteLocalTurns(targetId);
  conversations = conversations.filter((item) => item.id !== targetId);
  if (conversations.length) {
    const next = conversations.slice().sort((a, b) => b.updatedAt - a.updatedAt)[0];
    saveConversations();
    sessionId = next.id;
    localStorage.setItem(SESSION_KEY, sessionId);
    lastFixtureContext = restoreFixtureContext(next.matchContext);
    els.send.disabled = pendingChats.has(sessionId);
    renderConversations();
    await loadHistory();
  } else {
    createConversation();
  }
}
async function deleteAllConversations() {
  if (!confirm("¿Terminar y eliminar TODAS las conversaciones guardadas?")) return;
  const ids = conversations.map((item) => item.id);
  ids.forEach((id) => pendingChats.delete(id));
  await Promise.allSettled([
    ...ids.map((id) => api(`/api/history/${encodeURIComponent(id)}`, { method: "DELETE" })),
    ...ids.map((id) => deleteLocalTurns(id)),
  ]);
  conversations = [];
  createConversation();
}
function normalizeMention(text) {
  return String(text || "").toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/[^a-z0-9]+/g, " ").trim();
}
function findMentionedFixture(message) {
  const query = normalizeMention(message);
  const live = liveMatches.map(normalizeFixture);
  const candidates = [...upcomingFixtures, ...agendaFixtures, ...live, ...verifiedLaLigaFallbackFixtures()];
  const aliases = {
    "real madrid": ["real madrid", "madrid"],
    "celta vigo": ["celta vigo", "celta de vigo", "celta"],
    "atletico madrid": ["atletico madrid", "atletico de madrid", "atletico"],
    "athletic club": ["athletic club", "athletic bilbao"],
    "real betis": ["real betis", "betis"],
  };
  const mentionsTeam = (team) => {
    const name = normalizeMention(team);
    return (aliases[name] || [name]).some((alias) => (` ${query} `).includes(` ${alias} `));
  };
  const teams = (fixture) => [fixture.home, fixture.away].filter(Boolean);
  const both = candidates.find((fixture) => {
    const [home, away] = teams(fixture);
    return home && away && mentionsTeam(home) && mentionsTeam(away);
  });
  if (both) return both;
  if (lastFixtureContext && /este partido|ese partido|este encuentro|este juego|de ese partido|del partido/.test(query)) return lastFixtureContext;
  if (!/cuando|fecha|hora|proximo|proxima|juega|partido|enfrenta/.test(query)) return null;
  return candidates.find((fixture) => teams(fixture).some(mentionsTeam)) || null;
}
async function findNextFixtureForMessage(message) {
  const query = normalizeMention(message);
  const findTeams = () => Object.entries(catalog).flatMap(([leagueId, teams]) => {
    const league = LEAGUES.find((item) => item.id === leagueId);
    return (teams || []).filter((team) => {
      const name = normalizeMention(team.name);
      return name.length >= 2 && ` ${query} `.includes(` ${name} `);
    })
      .map((team) => ({ ...team, league }));
  }).sort((a, b) => b.name.length - a.name.length);
  let mentionedTeams = findTeams();
  const namesBothMentioned = /\b(vs|contra)\b/.test(query);
  if (!mentionedTeams.length || (namesBothMentioned && mentionedTeams.length < 2)) {
    const relevantLeagues = [selectedLeague];
    await Promise.all(relevantLeagues.map(async (league) => {
      if (catalog[league.id] || !league.season) return;
      try {
        const data = await api(`/api/football/teams?league=${encodeURIComponent(league.id)}&season=${encodeURIComponent(league.season)}`, { signal: AbortSignal.timeout(3000) });
        catalog[league.id] = data.teams || [];
        saveCachedCatalog(league.id, catalog[league.id]);
      } catch { /* se consultan las ligas restantes */ }
    }));
    mentionedTeams = findTeams();
  }
  if (!mentionedTeams.length || !/cuando|que dia|a que hora|fecha|horario|proxim|juega|partido|vs|contra|analiza/.test(query)) return null;
  const lead = mentionedTeams[0], league = lead.league;
  if (!league?.season) return null;
  try {
    const data = await api(`/api/football/team-fixtures?team_id=${encodeURIComponent(lead.id)}&season=${encodeURIComponent(league.season)}&limit=10`, { signal: AbortSignal.timeout(4000) });
    const fixtures = (Array.isArray(data.matches) ? data.matches : []).map(normalizeFixture);
    const opponent = mentionedTeams.find((team) => team.id !== lead.id);
    if (opponent) {
      const paired = fixtures.find((fixture) => [fixture.homeTeamId, fixture.awayTeamId].includes(String(lead.id))
        && [fixture.homeTeamId, fixture.awayTeamId].includes(String(opponent.id)));
      if (paired) return paired;
      const byName = fixtures.find((fixture) => {
        const names = [normalizeMention(fixture.home), normalizeMention(fixture.away)];
        return names.includes(normalizeMention(lead.name)) && names.includes(normalizeMention(opponent.name));
      });
      if (byName) return byName;
      return null;
    }
    return fixtures.find((fixture) => ["NS", "TBD", "PST", "UPCOMING"].includes(fixture.status.toUpperCase())) || fixtures[0] || null;
  } catch { return null; }
}
let pendingAttachment = null;
function updateComposerState() {
  const hasContent = Boolean(els.input.value.trim() || pendingAttachment);
  els.form?.classList.toggle("has-content", hasContent);
  $("#btn-attach")?.classList.toggle("has-attachment", Boolean(pendingAttachment));
}
function clearAttachment() {
  pendingAttachment = null;
  const box = $("#composer-attachment"), img = $("#composer-attachment-img"), input = $("#bet-image-input");
  if (box) box.hidden = true;
  if (img) img.removeAttribute("src");
  if (input) input.value = "";
  updateComposerState();
}
function attachBetImage(file) {
  if (!file || !file.type.startsWith("image/")) return;
  const objectUrl = URL.createObjectURL(file), image = new Image();
  image.onload = () => {
    const max = 1400, scale = Math.min(1, max / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.86);
    const [, base64] = dataUrl.split(",");
    pendingAttachment = { data: base64, mime_type: "image/jpeg", previewUrl: dataUrl, name: file.name || "apuesta.jpg" };
    const box = $("#composer-attachment"), img = $("#composer-attachment-img"), nameEl = $("#composer-attachment-name");
    if (img) img.src = dataUrl;
    if (nameEl) nameEl.textContent = pendingAttachment.name;
    if (box) box.hidden = false;
    updateComposerState();
    URL.revokeObjectURL(objectUrl);
    els.input.focus();
  };
  image.onerror = () => URL.revokeObjectURL(objectUrl);
  image.src = objectUrl;
}
async function sendMessage(text, { retry = false } = {}) {
  const rawMessage = text.trim();
  const modeHint = $("#risk-mode-select")?.value || "";
  const attachment = retry ? null : pendingAttachment;
  const message = rawMessage
    ? (modeHint ? `${rawMessage} (${modeHint})` : rawMessage)
    : (attachment && modeHint ? `Analiza esta foto de mi apuesta (${modeHint})` : "");
  const requestSessionId = sessionId;
  if ((!rawMessage && !attachment) || pendingChats.has(requestSessionId)) return;
  const normalizedMessage = normalizeMention(message);
  pendingChats.add(requestSessionId); els.send.disabled = true;
  const storedUserText = rawMessage || (attachment ? "📸 Foto de apuesta adjunta" : "");
  const localTurn = {
    localId: `t-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    id: null,
    user_message: storedUserText,
    user_image_data: attachment?.data || "",
    user_image_mime: attachment?.mime_type || "",
    imageUrl: attachment?.previewUrl || "",
    bot_response: "",
    active_rules: [],
    sources: [],
    fixture: null,
    isError: false,
    created_at: new Date().toISOString(),
  };
  if (!retry) {
    els.input.value = ""; autoResize(); clearAttachment();
    addUserMessage(storedUserText, localTurn.imageUrl);
    setConversationTitle(rawMessage || "Foto de apuesta");
    const conv = conversations.find((item) => item.id === requestSessionId);
    if (conv) { conv.updatedAt = Date.now(); saveConversations(); }
    const existingTurns = await readLocalTurns(requestSessionId);
    await writeLocalTurns(requestSessionId, [...existingTurns, localTurn]);
  }
  const typing = addTyping();
  try {
    let matchContext = message ? findMentionedFixture(message) : null;
    const needsFixtureLookup = /\b(cuando|que dia|a que hora|fecha|horario|proxim[oa]? partido|analiza (?:el )?partido|partido de|vs|contra)\b/.test(normalizedMessage);
    if (!matchContext && needsFixtureLookup) matchContext = await findNextFixtureForMessage(message);
    if (!matchContext && !/\b(vs|contra)\b/.test(normalizedMessage)) {
      matchContext = activeConversation()?.matchContext || lastFixtureContext;
    }
    if (matchContext) {
      lastFixtureContext = matchContext;
      const conversation = conversations.find((item) => item.id === requestSessionId);
      if (conversation) { conversation.matchContext = matchContext; conversation.updatedAt = Date.now(); saveConversations(); }
    }
    const data = await api("/api/chat", {
      method: "POST",
      signal: AbortSignal.timeout(attachment ? 55000 : 45000),
      body: JSON.stringify({
        message,
        session_id: requestSessionId,
        image: attachment ? { data: attachment.data, mime_type: attachment.mime_type } : null,
        match_context: matchContext ? {
          id: matchContext.id, home: matchContext.home, away: matchContext.away,
          home_logo: matchContext.homeLogo, away_logo: matchContext.awayLogo,
          competition: matchContext.competition,
          kickoff: matchContext.time?.toISOString() || "",
          status: matchContext.status,
        } : null,
      }),
    });
    typing.remove();
    const turnsNow = await readLocalTurns(requestSessionId);
    const idx = turnsNow.findIndex((t) => t.localId === localTurn.localId);
    const completedTurn = {
      ...(idx >= 0 ? turnsNow[idx] : localTurn),
      id: data.id ?? null,
      bot_response: data.answer || "",
      active_rules: data.active_rules || [],
      sources: data.sources || [],
      fixture: matchContext ? {
        id: matchContext.id, home: matchContext.home, away: matchContext.away,
        homeLogo: matchContext.homeLogo, awayLogo: matchContext.awayLogo,
        competition: matchContext.competition,
        time: matchContext.time?.toISOString() || "",
        status: matchContext.status,
      } : null,
      isError: false,
    };
    if (idx >= 0) turnsNow[idx] = completedTurn; else turnsNow.push(completedTurn);
    await writeLocalTurns(requestSessionId, turnsNow);
    if (sessionId === requestSessionId) addBotMessage(data, { fixture: matchContext });
  } catch (error) {
    typing.remove();
    const errorAnswer = "**No se completó la solicitud.** " + (error.name === "TimeoutError" ? "La solicitud tardó más de lo esperado. Puedes reintentar." : error.message);
    const turnsNow = await readLocalTurns(requestSessionId);
    const idx = turnsNow.findIndex((t) => t.localId === localTurn.localId);
    if (idx >= 0) {
      turnsNow[idx] = { ...turnsNow[idx], bot_response: errorAnswer, isError: true };
      await writeLocalTurns(requestSessionId, turnsNow);
    }
    if (sessionId === requestSessionId) addBotMessage({ answer: errorAnswer }, { isError: true, retryMessage: message });
  } finally {
    pendingChats.delete(requestSessionId);
    if (sessionId === requestSessionId) { els.send.disabled = false; els.input.focus(); }
  }
}
els.messages.addEventListener("click", (event) => {
  const img = event.target.closest(".msg__image");
  if (img) { openImageLightbox(img.src); return; }
  const retryButton = event.target.closest("[data-retry-message]");
  if (retryButton) sendMessage(retryButton.dataset.retryMessage, { retry: true });
});
function autoResize() {
  els.input.style.height = "36px";
  const next = Math.min(Math.max(els.input.scrollHeight, 36), 120);
  els.input.style.height = `${next}px`;
  els.input.style.overflowY = els.input.scrollHeight > 120 ? "auto" : "hidden";
  updateComposerState();
}

els.form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(els.input.value); });
$("#btn-attach")?.addEventListener("click", () => $("#bet-image-input")?.click());
$("#bet-image-input")?.addEventListener("change", (event) => attachBetImage(event.target.files?.[0]));
$("#composer-attachment-remove")?.addEventListener("click", clearAttachment);
els.input.addEventListener("paste", (event) => {
  const file = [...(event.clipboardData?.items || [])].find((item) => item.type.startsWith("image/"))?.getAsFile();
  if (file) { event.preventDefault(); attachBetImage(file); }
});
$("#new-conversation")?.addEventListener("click", createConversation);
$("#delete-conversation")?.addEventListener("click", deleteCurrentConversation);
$("#delete-all-conversations")?.addEventListener("click", deleteAllConversations);
$("#conversation-picker")?.addEventListener("change", (event) => switchConversation(event.target.value));
function applyPreferencesState(enabled) {
  const card = $(".preferences-card"), toggle = $(".preferences-card .switch");
  card?.classList.toggle("is-collapsed", !enabled);
  if (toggle) { toggle.setAttribute("aria-pressed", String(enabled)); toggle.setAttribute("aria-label", enabled ? "Desactivar preferencias" : "Activar preferencias"); }
  localStorage.setItem(PREFERENCES_ENABLED_KEY, String(enabled));
}
const preferencesToggle = $(".preferences-card .switch");
if (preferencesToggle) {
  applyPreferencesState(localStorage.getItem(PREFERENCES_ENABLED_KEY) !== "false");
  preferencesToggle.addEventListener("click", () => applyPreferencesState(preferencesToggle.getAttribute("aria-pressed") !== "true"));
}
els.input.addEventListener("input", autoResize);
els.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(els.input.value); } });
els.chips.addEventListener("click", (event) => { const chip = event.target.closest(".chip"); if (chip) sendMessage(chip.textContent); });
els.leagueList.addEventListener("click", (event) => { const button = event.target.closest("[data-league]"); if (button) loadLeague(button.dataset.league); });
els.teamSearch.addEventListener("input", () => renderTeams(catalog[selectedLeague.id] || []));
els.teamList.addEventListener("click", (event) => { const button = event.target.closest("[data-team]"); if (button) { els.input.value = `Analiza el próximo partido de ${button.dataset.team}`; autoResize(); els.input.focus(); $("#chat").scrollIntoView({ behavior: "smooth", block: "start" }); } });
function handleBadgeError(event) {
  const image = event.target.closest(".team-badge, .comparison-team-badge");
  if (!image) return;
  const alternate = image.dataset.fallback;
  if (alternate && image.dataset.fallbackTried !== "true") {
    image.dataset.fallbackTried = "true";
    image.src = alternate;
    return;
  }
  const fallback = document.createElement("span"); fallback.className = "team-placeholder"; fallback.textContent = image.dataset.initial || "⚽"; image.replaceWith(fallback);
}
els.teamList.addEventListener("error", handleBadgeError, true);
els.matches.addEventListener("error", handleBadgeError, true);
$("#comparison-results").addEventListener("error", handleBadgeError, true);
function useMatch(event) { const card = event.target.closest(".match-card"); if (!card) return; const fixture = agendaFixtures.find((item) => item.id === card.dataset.fixtureId); if (fixture) { lastFixtureContext = fixture; const conversation = activeConversation(); if (conversation) { conversation.matchContext = fixture; saveConversations(); } } els.input.value = card.dataset.q; autoResize(); els.input.focus(); $("#chat").scrollIntoView({ behavior: "smooth", block: "start" }); }
els.matches.addEventListener("click", useMatch);
els.matches.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); useMatch(event); } });
els.menu.addEventListener("click", () => { const sidebar = $("#ligas"), open = sidebar.classList.toggle("mobile-open"); els.menu.setAttribute("aria-expanded", String(open)); });

function setView(view) {
  const isLive = view === "live";
  const isUpcoming = view === "upcoming";
  const isAdvanced = view === "advanced";
  const isProfile = view === "profile";
  const viewSelect = $("#mobile-view-select");
  if (viewSelect) viewSelect.value = view;
  $("#home-view").hidden = isLive || isUpcoming || isAdvanced || isProfile;
  $("#live-view").hidden = !isLive;
  $("#upcoming-view").hidden = !isUpcoming;
  $("#advanced-view").hidden = !isAdvanced;
  $("#profile-view").hidden = !isProfile;
  document.querySelectorAll(".main-nav [data-view]").forEach((link) => link.classList.toggle("active", link.dataset.view === view));
  document.querySelectorAll(".mobile-bottom-nav [data-view]").forEach((link) => {
    const active = link.dataset.view === view;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  if (liveRefreshTimer) { clearInterval(liveRefreshTimer); liveRefreshTimer = null; }
  if (upcomingTimer) { clearInterval(upcomingTimer); upcomingTimer = null; }
  if (isLive) {
    loadLiveMatches();
    liveRefreshTimer = setInterval(loadLiveMatches, 60_000);
  }
  if (isUpcoming) {
    loadUpcomingFixtures();
    upcomingTimer = setInterval(loadUpcomingFixtures, 5 * 60_000);
  }
  if (isAdvanced) { loadAnalytics(); loadFootballCharts(); }
  if (isProfile) renderProfile();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
document.querySelectorAll("[data-view]").forEach((control) => control.addEventListener("click", (event) => {
  const view = control.dataset.view;
  if (!view) return;
  event.preventDefault();
  setView(view);
}));
$("#league-search").addEventListener("input", renderLeagues);
$(".profile-button").addEventListener("click", () => setView("profile"));

function liveStatus(match) {
  return `${match.status || ""} ${match.status_text || ""}`.trim().toLocaleLowerCase("en");
}
function statusIndicatesLive(match) {
  const status = liveStatus(match);
  if (/finished|full.?time|\bft\b|ended|cancelled|postponed|not started/.test(status)) return false;
  return /live|in.?play|progress|half.?time|\bht\b|extra.?time|penalt|\d{1,3}(?:\+\d+)?\s*['’]/.test(status);
}
function isLive(match) { return liveFeedFresh && statusIndicatesLive(match); }
function isFinished(match) { return /finished|full.?time|\bft\b|\baet\b|\bpen\b|ended/.test(liveStatus(match)); }
function matchSlug(match) {
  if (match.slug) return String(match.slug);
  if (match.id) return String(match.id);
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
      ? "No hay partidos en juego ahora en las competiciones seguidas. Los marcadores se actualizarán automáticamente."
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
    return `<article class="live-match-card ${selected ? "selected" : ""}" tabindex="0" role="button" data-live-slug="${escapeHtml(slug)}" aria-label="Ver ${escapeHtml(match.home)} contra ${escapeHtml(match.away)}"><div class="live-card-league">${leagueLogo ? `<img src="${leagueLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "⚽"}<span>${escapeHtml(match.competition || "Fútbol")}</span></div><div class="live-card-score"><div class="live-card-team">${homeLogo ? `<img src="${homeLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(String(match.home || "L").slice(0,1))}</span>`}<span>${escapeHtml(match.home || "Local")}</span></div><div class="live-score">${escapeHtml(match.home_score ?? "–")} - ${escapeHtml(match.away_score ?? "–")}<small class="live-status ${isFinished(match) ? "finished" : live ? "" : "scheduled"}">${escapeHtml(clock)}</small></div><div class="live-card-team away">${awayLogo ? `<img src="${awayLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(String(match.away || "V").slice(0,1))}</span>`}<span>${escapeHtml(match.away || "Visitante")}</span></div></div><div class="live-card-footer"><span>${live ? "● EN DIRECTO" : isFinished(match) ? "JORNADA FINALIZADA" : "PARTIDO"}</span><strong>${escapeHtml(clock)}</strong></div></article>`;
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
function renderLiveSimulation(match, details) {
  if (!isLive(match)) return "";
  const rawEvents = details && Array.isArray(details.events) ? details.events : [];
  const events = rawEvents.map((event) => {
    const text = String(event.text || "");
    const minute = Number.parseInt(String(event.time || event.minute || "").match(/\d+/)?.[0] || "", 10);
    const kind = /goal|gol|penalty|own goal/i.test(text) ? "goal" : /card|tarjeta/i.test(text) ? "card" : /subst|sustituci/i.test(text) ? "sub" : "event";
    return { minute, text, kind };
  }).filter((event) => Number.isFinite(event.minute));
  const minute = Number(match.elapsed ?? String(match.status_text || "").match(/\d+/)?.[0] ?? 0);
  const progress = Math.min(100, Math.max(0, minute / 90 * 100));
  const markers = events.map((event) => `<span class="simulation-event ${event.kind}" style="left:${Math.min(100, Math.max(0, event.minute / 90 * 100))}%" title="${escapeHtml(`${event.minute}′ ${event.text}`)}">${event.kind === "goal" ? "⚽" : event.kind === "card" ? "▰" : "•"}</span>`).join("");
  const eventList = events.length
    ? events.slice(-4).reverse().map((event) => `<li><time>${event.minute}′</time><span>${escapeHtml(event.text)}</span></li>`).join("")
    : `<li class="simulation-no-events">Aún no hay eventos registrados.</li>`;
  return `<section class="live-simulation" aria-label="Simulación visual del partido"><div class="simulation-heading"><div><strong>Simulación del partido</strong><small>Marcador y eventos reportados por la API</small></div><span class="simulation-clock">${escapeHtml(match.status_text || `${minute}′`)}</span></div><div class="simulation-score"><span>${escapeHtml(match.home)}</span><strong>${escapeHtml(match.home_score ?? "–")} : ${escapeHtml(match.away_score ?? "–")}</strong><span>${escapeHtml(match.away)}</span></div><div class="simulation-timeline" role="img" aria-label="Partido en el minuto ${minute} de 90"><span>0′</span><div class="simulation-track"><i style="width:${progress}%"></i>${markers}<b style="left:${progress}%"></b></div><span>90′</span></div><ul class="simulation-events">${eventList}</ul><p>Vista gráfica del reloj y los eventos registrados. No es video ni muestra la ubicación real del balón.</p></section>`;
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
  $("#live-details").innerHTML = `<h3 class="selected-match-title">${escapeHtml(match.home)} vs ${escapeHtml(match.away)}</h3><p class="selected-match-comp">${escapeHtml(match.competition || "Fútbol")} · ${escapeHtml(formatMatchClock(match))}</p><div class="detail-score">${homeLogoMarkup}<strong>${escapeHtml(match.home_score ?? "–")} : ${escapeHtml(match.away_score ?? "–")}</strong>${awayLogoMarkup}</div><div class="detail-team-names"><span>${escapeHtml(match.home)}</span><span>${escapeHtml(match.away)}</span></div>${statsMarkup}${eventsMarkup}${renderLiveSimulation(match, details)}`;
}
async function loadLiveDetails(slug) {
  const match = liveMatches.find((item) => matchSlug(item) === slug);
  selectedLiveSlug = slug;
  selectedLiveDetails = null;
  renderLiveMatches();
  renderLiveDetails(match);
  if (!slug) return;
  try {
    const response = await fetch(`${API_BASE}/api/football/fixtures/${encodeURIComponent(slug)}`, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (selectedLiveSlug === slug) { selectedLiveDetails = payload; renderLiveDetails(match, selectedLiveDetails); }
  } catch {
    if (selectedLiveSlug === slug) { selectedLiveDetails = {}; renderLiveDetails(match, selectedLiveDetails); }
  }
}
async function loadLiveMatches() {
  const refreshButton = $("#live-refresh");
  refreshButton.classList.add("is-loading");
  try {
    const response = await fetch(`${API_BASE}/api/football/live`, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(12000) });
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
      if (selected && isLive(selected)) void loadLiveDetails(selectedLiveSlug);
      else if (selected) renderLiveDetails(selected, selectedLiveDetails);
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

function loadFavoriteLeagues() {
  try {
    const saved = JSON.parse(localStorage.getItem("statstriker_favorite_leagues") || "null");
    return Array.isArray(saved) ? saved : ["4328", "4335"];
  } catch { return ["4328", "4335"]; }
}
function saveFavoriteLeagues() { localStorage.setItem("statstriker_favorite_leagues", JSON.stringify(favoriteLeagueIds)); }
function loadFavoriteTeams() {
  try {
    const saved = JSON.parse(localStorage.getItem(FAVORITE_TEAM_KEY) || "[]");
    return Array.isArray(saved) ? saved.filter((team) => team && team.id && team.name && team.leagueId && team.season) : [];
  } catch { return []; }
}
function saveFavoriteTeams() { localStorage.setItem(FAVORITE_TEAM_KEY, JSON.stringify(favoriteTeams)); }
function bogotaDate(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}
function shiftDate(date, amount) { const shifted = new Date(`${date}T12:00:00Z`); shifted.setUTCDate(shifted.getUTCDate() + amount); return shifted.toISOString().slice(0, 10); }
function cachedUpcoming(day = selectedFixtureDate) {
  try {
    const cached = JSON.parse(localStorage.getItem(FIXTURE_CACHE_KEY) || "null");
    const entry = cached?.[day];
    return entry && Date.now() - entry.savedAt < FIXTURE_CACHE_TTL && Array.isArray(entry.matches) ? entry.matches : null;
  } catch { return null; }
}
function storeUpcoming(matches, day = selectedFixtureDate) {
  try {
    const cache = JSON.parse(localStorage.getItem(FIXTURE_CACHE_KEY) || "{}");
    cache[day] = { savedAt: Date.now(), matches };
    const days = Object.keys(cache).sort((a, b) => cache[b].savedAt - cache[a].savedAt);
    days.slice(30).forEach((key) => delete cache[key]);
    localStorage.setItem(FIXTURE_CACHE_KEY, JSON.stringify(cache));
  } catch { /* caché opcional */ }
}
function fixtureArray(payload) {
  for (const key of ["fixtures", "matches", "events", "results", "data"]) {
    if (Array.isArray(payload?.[key])) return payload[key];
    if (Array.isArray(payload?.data?.[key])) return payload.data[key];
  }
  return [];
}
function fixtureTeamName(fixture, side) {
  const value = fixture[side] || fixture[`${side}_team`] || fixture[`${side}_team_name`] || fixture[`${side}Team`] || fixture[`${side}TeamName`] || fixture.teams?.[side] || fixture.participants?.[side];
  return typeof value === "string" ? value : value?.name || value?.team_name || "";
}
function fixtureTeamLogo(fixture, side) {
  const value = fixture[`${side}_logo`] || fixture[`${side}Logo`] || fixture[`${side}LogoUrl`] || fixture.teams?.[side]?.logo || fixture.teams?.[side]?.image;
  return safeImage(typeof value === "string" ? value : value?.url);
}
function normalizeFixture(fixture) {
  let time = fixture.kickoff || fixture.start_time || fixture.startTime || fixture.utcDate || fixture.match_start || fixture.start_at || fixture.datetime || fixture.time || fixture.date || fixture.dateEvent;
  const datePart = fixture.date || fixture.dateEvent;
  const timePart = fixture.time || fixture.strTime || fixture.hour;
  if (datePart && /^\d{4}-\d{2}-\d{2}$/.test(String(datePart)) && timePart && /^\d{1,2}:\d{2}/.test(String(timePart))) time = `${datePart}T${timePart}`;
  const home = fixtureTeamName(fixture, "home"), away = fixtureTeamName(fixture, "away");
  const competitionValue = fixture.competition || fixture.league || fixture.tournament || fixture.competition_name || fixture.league_name || fixture.strLeague || "Football";
  const competition = typeof competitionValue === "string" ? competitionValue : competitionValue?.name || "Football";
  const country = fixture.country || fixture.competition_country || fixture.league?.country || "";
  const competitionLabel = country && !competition.toLocaleLowerCase("es").includes(country.toLocaleLowerCase("es")) ? `${competition} | ${country}` : competition;
  return {
    id: String(fixture.id || fixture.slug || `${home}-${away}-${time || ""}`), slug: fixture.slug || "",
    home, away, homeLogo: fixtureTeamLogo(fixture, "home"), awayLogo: fixtureTeamLogo(fixture, "away"),
    competition: competitionLabel,
    competitionId: String(fixture.competition_id || fixture.league?.id || ""),
    competitionLogo: safeImage(fixture.competitionLogo || fixture.competition_logo || fixture.league_logo || fixture.competition?.logo),
    round: fixture.round || fixture.league?.round || "",
    homeTeamId: String(fixture.home_id || fixture.teams?.home?.id || ""),
    awayTeamId: String(fixture.away_id || fixture.teams?.away?.id || ""),
    time: parseFixtureTime(time), status: String(fixture.status || fixture.state || "upcoming"),
    statusText: String(fixture.status_text || fixture.statusText || ""),
    homeScore: fixture.home_score ?? fixture.goals?.home ?? null,
    awayScore: fixture.away_score ?? fixture.goals?.away ?? null,
    venue: fixture.venue || fixture.stadium || "", odds: fixture.odds || fixture.bookmakers || null,
  };
}
function parseFixtureTime(value) {
  if (!value) return null;
  const text = String(value).trim();
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(text) ? `${text}Z` : text;
  const date = new Date(normalized);
  return Number.isNaN(date.valueOf()) ? null : date;
}
function fixtureLeagueId(competition) {
  const name = String(competition || "").toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "");
  const match = LEAGUES.filter((league) => name.includes(league.name.toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "")))
    .sort((a, b) => b.name.length - a.name.length)[0];
  if (match) return match.id;
  const aliases = { "39": ["premier league", "english premier", "inglaterra"], "140": ["laliga", "la liga", "spanish la"], "135": ["serie a", "italian serie", "italia"], "78": ["bundesliga", "german bundes", "alemania"], "61": ["ligue 1", "french ligue", "francia"], "2": ["champions league", "uefa champions"], "3": ["europa league", "uefa europa"], "13": ["libertadores", "conmebol libertadores"], "71": ["brasileirao", "brazilian serie a"], "253": ["major league soccer", "mls"] };
  return Object.entries(aliases).find(([, words]) => words.some((word) => name.includes(word)))?.[0] || "other";
}
function fixtureCountryId(competition) {
  const name = String(competition || "").toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "");
  const match = COUNTRIES.find((country) => name.includes(country.name.toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "")));
  return match?.id || "";
}
function isFavoriteFixture(competition, countries = readProfileData().countries || []) {
  return favoriteLeagueIds.includes(fixtureLeagueId(competition)) || countries.includes(fixtureCountryId(competition));
}
function isFavoriteTeamFixture(fixture) {
  const teamNames = [fixture.home, fixture.away].map((name) => String(name || "").toLocaleLowerCase("es"));
  const teamIds = [fixture.homeTeamId, fixture.awayTeamId].map(String);
  return favoriteTeams.some((team) => teamNames.includes(String(team.name).toLocaleLowerCase("es")) || teamIds.includes(String(team.id)));
}
function fixtureLocalDate(fixture) { return fixture.time && !Number.isNaN(fixture.time.valueOf()) ? bogotaDate(fixture.time) : ""; }
function fixtureClock(fixture) {
  if (!fixture.time || Number.isNaN(fixture.time.valueOf())) return "Hora pendiente";
  return new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", hour: "2-digit", minute: "2-digit" }).format(fixture.time);
}
function fixtureLongDate(fixture) {
  if (!fixture.time || Number.isNaN(fixture.time.valueOf())) return "Fecha por confirmar";
  return new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(fixture.time);
}
function selectedDateLabel() {
  const date = new Date(`${selectedFixtureDate}T17:00:00Z`);
  return new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(date);
}
function renderFixtureCard(fixture) {
  const favorite = isFavoriteFixture(fixture.competition);
  const competitionLogo = fixture.competitionLogo ? `<img src="${fixture.competitionLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "⚽";
  const homeLogo = fixture.homeLogo ? `<img src="${fixture.homeLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(fixture.home.slice(0, 1))}</span>`;
  const awayLogo = fixture.awayLogo ? `<img src="${fixture.awayLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(fixture.away.slice(0, 1))}</span>`;
  const status = fixture.status.toUpperCase();
  const final = ["FT", "AET", "PEN"].includes(status);
  const live = ["LIVE", "1H", "2H", "HT", "ET", "BT", "P"].includes(status);
  const tag = /postpon|^pst$/.test(status.toLowerCase()) ? "Reprogramado" : final ? "Finalizado" : live ? "En vivo" : status === "CANC" ? "Cancelado" : "Programado";
  const center = final && fixture.homeScore != null && fixture.awayScore != null
    ? `${fixture.homeScore} – ${fixture.awayScore}` : live ? fixture.statusText || "En vivo" : fixtureClock(fixture);
  const recommendation = quickAnalysisState.suggestions.find((item) => item.fixture_id === fixture.id);
  const recommendationText = recommendation
    ? `<div class="fixture-recommendation"><strong>Opción a revisar: ${escapeHtml(recommendation.title || "Análisis disponible")}</strong><span>${escapeHtml(recommendation.summary || "Revisa los datos disponibles antes de elegir un mercado.")}</span></div>`
    : `<div class="fixture-recommendation"><strong>${quickAnalysisState.loading ? "Analizando este partido…" : quickAnalysisState.error ? "Mercados para revisar con datos limitados" : "Mercados para evaluar"}</strong><span>${quickAnalysisState.error ? "Consulta las estadísticas disponibles antes de elegir un mercado." : "1X2, Más o Menos de 2.5 goles y Ambos equipos marcan"}</span></div>`;
  return `<article class="fixture-card ${favorite ? "is-favorite" : ""}"><div class="fixture-card-top"><span class="fixture-league">${competitionLogo}${escapeHtml(fixture.competition)}</span><span class="fixture-status">${tag}</span></div><div class="fixture-matchup"><div class="fixture-club">${homeLogo}<span>${escapeHtml(fixture.home)}</span></div><div class="fixture-kickoff"><strong>${escapeHtml(center)}</strong><small>${escapeHtml(fixtureLongDate(fixture) + " - hora de Colombia")}</small></div><div class="fixture-club away">${awayLogo}<span>${escapeHtml(fixture.away)}</span></div></div><div class="fixture-card-meta"><span>${fixture.venue ? `⌖ ${escapeHtml(fixture.venue)}` : "Calendario oficial"}</span>${favorite ? `<span class="favorite-tag">★ En favoritos</span>` : ""}</div><div class="fixture-recommendation-label">Análisis del partido y mercados</div><div class="fixture-markets"><span>1X2</span><span>Más/Menos 2.5</span><span>Ambos marcan</span></div>${recommendationText}<button class="fixture-analysis-button" type="button" data-analyze-fixture="${escapeHtml(fixture.id)}">Analizar con Chatbot <span>↗</span></button></article>`;
}
function renderFavoriteLeagues() {
  const host = $("#favorite-leagues");
  const featured = LEAGUES;
  const selected = LEAGUES.filter((league) => favoriteLeagueIds.includes(league.id));
  const quickChoices = [...new Map([...featured, ...selected].map((league) => [league.id, league])).values()];
  host.innerHTML = quickChoices.map((league) => {
    const logo = safeImage(league.logo);
    const icon = logo ? `<img class="favorite-league-logo" src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "";
    return `<label class="favorite-league"><input type="checkbox" value="${escapeHtml(league.id)}" ${favoriteLeagueIds.includes(league.id) ? "checked" : ""}><span class="favorite-check">&#10003;</span>${icon}<span class="favorite-name">${escapeHtml(league.name)}</span><i class="favorite-dot ${favoriteLeagueIds.includes(league.id) ? "on" : ""}"></i></label>`;
  }).join("");
  const select = $("#fixture-league-filter"), current = select.value;
  select.innerHTML = `<option value="all">Todas las ligas</option>${LEAGUES.map((league) => `<option value="${escapeHtml(league.id)}">${escapeHtml(`${league.name} (${countryLabel(league.country)})`)}</option>`).join("")}`;
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}
let recommendedTeamsRequest = 0;
function renderRecommendedTeams(groups) {
  const host = $("#recommended-teams-list");
  recommendedTeamGroups = groups;
  if (!groups.length) {
    host.innerHTML = `<p class="no-analysis">Selecciona una liga favorita para ver los tres primeros equipos de su tabla.</p>`;
    return;
  }
  host.innerHTML = groups.map(({ league, teams, error }) => {
    const hasVerifiedRanks = (teams || []).some((team) => Number.isInteger(team.rank));
    const rows = (teams || []).map((team) => {
      const logo = safeImage(team.logo);
      const preferredTeam = { id: String(team.team_id || team.id || ""), name: team.name, badge: team.logo || "", leagueId: String(league.id), leagueName: league.name, season: league.season };
      const key = `${preferredTeam.leagueId}:${preferredTeam.id}`;
      const isPreferred = favoriteTeams.some((item) => `${item.leagueId}:${item.id}` === key);
      return `<div class="recommended-team-row"><span class="recommended-rank">${escapeHtml(String(team.rank || "–"))}</span>${logo ? `<img src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(team.name.slice(0, 1))}</span>`}<strong>${escapeHtml(team.name)}</strong><small>${team.points == null ? "" : `${escapeHtml(String(team.points))} pts`}</small><button class="team-favorite-toggle ${isPreferred ? "is-preferred" : ""}" type="button" data-favorite-team="${escapeHtml(JSON.stringify(preferredTeam))}" aria-label="${isPreferred ? "Quitar de" : "Agregar a"} mis equipos preferidos" aria-pressed="${isPreferred}">${isPreferred ? "★" : "☆"}</button></div>`;
    }).join("");
    const descriptions = (teams || []).map((team) => String(team.description || "").toLocaleLowerCase("es"));
    const isPartial = descriptions.some((description) => description.includes("parcial"));
    const isCatalog = descriptions.some((description) => description.includes("no se pudo verificar"));
    const basis = isPartial ? `<small class="recommended-basis">Clasificación parcial · partidos con resultado</small>` : isCatalog ? `<small class="recommended-basis">Equipos destacados · posiciones actuales por confirmar</small>` : "";
    const title = hasVerifiedRanks ? league.name : `${league.name} · equipos destacados`;
    return `<section class="recommended-league"><h3>${escapeHtml(title)}</h3>${basis}${rows || `<p class="no-analysis">Sigue la liga y compara sus equipos desde Estadísticas.</p>`}</section>`;
  }).join("");
}
async function loadRecommendedTeams(ids = favoriteLeagueIds) {
  const token = ++recommendedTeamsRequest;
  const selected = LEAGUES.filter((league) => league.id !== "143" && ids.includes(league.id) && league.season).slice(0, 10);
  if (!selected.length) { renderRecommendedTeams([]); await loadMatches(); return []; }
  const cacheKey = "statstriker_recommended_teams_v2";
  let cache = {};
  try { cache = JSON.parse(localStorage.getItem(cacheKey) || "{}"); } catch { cache = {}; }
  const cachedGroups = selected.filter((league) => cache[`${league.id}:${league.season}`]?.expires > Date.now())
    .map((league) => ({ league, teams: cache[`${league.id}:${league.season}`].teams }))
    .filter((group) => group.teams.length);
  if (cachedGroups.length) renderRecommendedTeams(cachedGroups);
  else $("#recommended-teams-list").innerHTML = `<p class="no-analysis">Consultando las tablas de tus ligas…</p>`;
  const freshGroups = [];
  for (const league of selected) {
    try {
      const data = await api(`/api/football/standings?league=${encodeURIComponent(league.id)}&season=${encodeURIComponent(league.season)}`);
      const teams = Array.isArray(data.teams) ? data.teams : [];
      if (teams.length) cache[`${league.id}:${league.season}`] = { expires: Date.now() + 6 * 60 * 60 * 1000, teams };
      else delete cache[`${league.id}:${league.season}`];
      freshGroups.push({ league, teams });
    } catch {
      const old = cache[`${league.id}:${league.season}`];
      freshGroups.push({ league, teams: old?.teams || [], error: true });
    }
  }
  try { localStorage.setItem(cacheKey, JSON.stringify(cache)); } catch { /* almacenamiento opcional */ }
  if (token === recommendedTeamsRequest) {
    renderRecommendedTeams(freshGroups);
    await loadMatches();
  }
  return freshGroups;
}
function renderQuickAnalysis(fixtures) {
  const host = $("#quick-analysis-list");
  const selected = fixtures.slice(0, 10);
  if (!selected.length) {
    quickAnalysisState = { key: "", loading: false, error: "", suggestions: [] };
    host.innerHTML = `<p class="no-analysis">Las recomendaciones por partido aparecerán cuando haya encuentros en agenda.</p>`;
    return;
  }
  const key = selected.map((fixture) => fixture.id).join("|");
  if (key !== quickAnalysisState.key) {
    quickAnalysisState = { key, loading: true, error: "", suggestions: [] };
    host.innerHTML = `<p class="no-analysis">Preparando recomendaciones para ${selected.length} partidos…</p>`;
    requestQuickAnalysis(selected, key);
    return;
  }
  if (quickAnalysisState.loading) {
    host.innerHTML = `<p class="no-analysis">Preparando recomendaciones para ${selected.length} partidos…</p>`;
    return;
  }
  if (quickAnalysisState.error) {
    host.innerHTML = `<p class="no-analysis">Usa estos mercados como referencia y revisa primero las estadísticas disponibles.</p>`;
    return;
  }
  const suggestions = new Map(quickAnalysisState.suggestions.map((item) => [item.fixture_id, item]));
  host.innerHTML = selected.map((fixture) => {
    const suggestion = suggestions.get(fixture.id) || {};
    const logo = fixture.homeLogo ? `<img src="${fixture.homeLogo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(fixture.home.slice(0, 1))}</span>`;
    const quality = suggestion.data_quality === "suficiente" ? "Datos disponibles" : "Datos limitados";
    return `<button class="quick-analysis-item" type="button" data-analyze-fixture="${escapeHtml(fixture.id)}"><span class="quick-analysis-logo">${logo}</span><span class="quick-analysis-copy"><strong>${escapeHtml(fixture.home)} vs ${escapeHtml(fixture.away)}</strong><small>${escapeHtml(fixture.competition)} | ${escapeHtml(fixtureClock(fixture))}</small><b>${escapeHtml(suggestion.title || "Mercados para comparar")}</b><small>${escapeHtml(suggestion.summary || "Compara forma, alineaciones y cuotas antes de elegir.")}</small><em>${quality} | Análisis del partido</em></span><span class="quick-analysis-arrow">&#8250;</span></button>`;
  }).join("");
}
async function requestQuickAnalysis(fixtures, key) {
  const request = {
    fixtures: fixtures.map((fixture) => ({
      id: fixture.id, home: fixture.home, away: fixture.away,
      competition: fixture.competition, kickoff: fixture.time?.toISOString() || "",
      status: fixture.status || "NS",
    })),
  };
  try {
    const data = await api("/api/quick-analysis", { method: "POST", body: JSON.stringify(request), signal: AbortSignal.timeout(35000) });
    if (quickAnalysisState.key !== key) return;
    quickAnalysisState = { key, loading: false, error: "", suggestions: data.suggestions || [] };
  } catch (error) {
    if (quickAnalysisState.key !== key) return;
    quickAnalysisState = { key, loading: false, error: error.message || "No se pudo cargar el análisis.", suggestions: [] };
  }
  renderQuickAnalysis(fixtures);
  if (selectedFixtureDate && upcomingFixtures.length) renderUpcomingFixtures();
}
function renderUpcomingFixtures() {
  const search = $("#fixture-search").value.trim().toLocaleLowerCase("es");
  const league = $("#fixture-league-filter").value;
  const favoriteCountries = readProfileData().countries || [];
  const matches = upcomingFixtures.filter((fixture) => {
    const day = fixtureLocalDate(fixture), leagueId = fixtureLeagueId(fixture.competition);
    const textMatch = `${fixture.home} ${fixture.away} ${fixture.competition}`.toLocaleLowerCase("es").includes(search);
    return day === selectedFixtureDate && textMatch && (league === "all" || leagueId === league);
  });
  if ($("#fixture-sort").value === "league") matches.sort((a, b) => a.competition.localeCompare(b.competition, "es") || a.time - b.time);
  else matches.sort((a, b) => Number(isFavoriteTeamFixture(b)) - Number(isFavoriteTeamFixture(a)) || Number(isFavoriteFixture(b.competition, favoriteCountries)) - Number(isFavoriteFixture(a.competition, favoriteCountries)) || a.time - b.time);
  $("#fixture-count-label").textContent = matches.length ? `${matches.length} partidos en esta fecha` : "No hay partidos para esta selección";
  $("#fixture-date-label").textContent = `Agenda · ${selectedDateLabel()}`;
  $("#fixtures-grid").innerHTML = matches.length ? matches.map(renderFixtureCard).join("") : `<div class="live-empty"><span class="stat-ring">▦</span><strong>Sin partidos para esta fecha</strong><p>Elige otro día del calendario anual o actualiza la consulta.</p></div>`;
  renderQuickAnalysis(matches.filter((fixture) => ["NS", "TBD", "PST", "UPCOMING"].includes(fixture.status.toUpperCase()) || /not started|scheduled|program|postpon|upcoming/i.test(fixture.status)));
}
async function loadUpcomingFixtures(force = false) {
  const requestId = ++upcomingRequestId;
  const requestedDate = selectedFixtureDate;
  const button = $("#fixture-refresh");
  button.classList.add("is-loading");
  if (!force) {
    const cached = cachedUpcoming(requestedDate);
    if (cached) { upcomingFixtures = cached.map(normalizeFixture); renderUpcomingFixtures(); button.classList.remove("is-loading"); return; }
  }
  try {
    const preferredLeagues = [...new Set([...favoriteLeagueIds, ...favoriteTeams.map((team) => String(team.leagueId))])].filter((id) => FEATURED_LEAGUE_IDS.includes(id));
    const params = new URLSearchParams({ from_date: requestedDate, to_date: requestedDate, leagues: preferredLeagues.join(",") });
    const response = await fetch(`${API_BASE}/api/football/fixtures?${params}`, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(15000) });
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      throw new Error(failure.detail || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    if (requestId !== upcomingRequestId) return;
    const seen = new Set();
    upcomingFixtures = fixtureArray(payload).map(normalizeFixture).filter((fixture) => {
      const day = fixtureLocalDate(fixture), key = `${fixture.home}|${fixture.away}|${fixture.time?.toISOString() || ""}`;
      if (!fixture.home || !fixture.away || !fixture.time || Number.isNaN(fixture.time.valueOf()) || day !== requestedDate || seen.has(key)) return false;
      seen.add(key); return true;
    });
    storeUpcoming(upcomingFixtures, requestedDate);
    const datesAvailable = [...new Set(upcomingFixtures.map(fixtureLocalDate))].length;
    $("#fixture-updated").textContent = `Calendario actualizado · hora de Colombia · ${datesAvailable ? "API-Football" : "sin partidos para esta fecha"}`;
    renderFavoriteLeagues(); renderUpcomingFixtures();
  } catch (error) {
    if (requestId !== upcomingRequestId) return;
    if (!upcomingFixtures.length) {
      renderQuickAnalysis([]);
      $("#fixtures-grid").innerHTML = `<div class="live-empty"><strong>No se pudo cargar el calendario</strong><p>Comprueba la conexión y vuelve a intentarlo. No se muestran partidos de demostración como si fueran próximos.</p></div>`;
      $("#fixture-count-label").textContent = "Calendario no disponible";
    } else $("#fixture-updated").textContent = "No se pudo actualizar · se muestran los datos guardados";
  } finally { if (requestId === upcomingRequestId) button.classList.remove("is-loading"); }
}
function selectedAnalyticsFixture() { return analyticsData?.matches.find((match) => match.id === selectedAnalyticsMatch) || analyticsData?.matches[0] || null; }
function normalizeClubName(name) { return String(name || "").toLocaleLowerCase("es").replace(/^(fc|afc|ac|as|ssc|real|club)\s+/g, "").replace(/[^a-z0-9]/g, ""); }
function analyticsTeamLogo(name) {
  const target = normalizeClubName(name);
  for (const teams of Object.values(catalog)) {
    const found = teams.find((team) => {
      const candidate = normalizeClubName(team.name);
      return candidate === target || (Math.min(candidate.length, target.length) > 5 && (candidate.includes(target) || target.includes(candidate)));
    });
    if (found?.badge) return safeImage(found.badge);
  }
  return "";
}
function renderApiBarRows(selector, rows, emptyText) {
  const host = $(selector);
  if (!rows.length) { host.innerHTML = `<p class="api-chart-empty">${escapeHtml(emptyText)}</p>`; return; }
  const max = Math.max(1, ...rows.map((row) => row.value));
  host.innerHTML = rows.map((row) => `<div class="api-bar-row"><div class="api-bar-label"><span>${escapeHtml(row.label)}</span><strong>${row.value}</strong></div><div class="api-bar-track"><i class="${row.kind || ""}" style="width:${Math.max(row.value ? 5 : 0, row.value / max * 100)}%"></i></div></div>`).join("");
}
function renderApiLeagueRows(groups) {
  const host = $("#api-league-chart");
  const rows = [...groups.entries()].map(([label, values]) => ({ label, ...values, total: values.upcoming + values.live })).sort((a, b) => b.total - a.total).slice(0, 6);
  if (!rows.length) { host.innerHTML = `<p class="api-chart-empty">No hay partidos disponibles en el rango actual.</p>`; return; }
  const maxUpcoming = Math.max(1, ...rows.map((row) => row.upcoming)), maxLive = Math.max(1, ...rows.map((row) => row.live));
  host.innerHTML = rows.map((row) => `<div class="api-league-row"><div class="api-bar-label"><span>${escapeHtml(row.label)}</span><strong>${row.upcoming} / ${row.live}</strong></div><div class="api-league-bars"><i class="api-upcoming-bar" style="width:${row.upcoming ? Math.max(5, row.upcoming / maxUpcoming * 100) : 0}%"></i><i class="api-live-bar" style="width:${row.live ? Math.max(5, row.live / maxLive * 100) : 0}%"></i></div></div>`).join("");
}
async function loadFootballCharts() {
  const status = $("#api-charts-updated");
  if (!status) return;
  status.textContent = "Cargando datos de API-Football...";
  const today = bogotaDate(), tomorrow = shiftDate(today, 1);
  const params = new URLSearchParams({ from_date: today, to_date: tomorrow });
  try {
    const [liveResult, scheduleResult] = await Promise.allSettled([
      api("/api/football/live"),
      api(`/api/football/fixtures?${params}`),
    ]);
    if (liveResult.status === "rejected") throw liveResult.reason;
    const live = (liveResult.value.matches || []).map(normalizeFixture);
    const scheduled = scheduleResult.status === "fulfilled"
      ? fixtureArray(scheduleResult.value).map(normalizeFixture).filter((match) => ["NS", "TBD", "PST"].includes(match.status.toUpperCase()))
      : [];
    const groups = new Map();
    for (const match of scheduled) {
      const row = groups.get(match.competition) || { upcoming: 0, live: 0 };
      row.upcoming += 1; groups.set(match.competition, row);
    }
    for (const match of live) {
      const row = groups.get(match.competition) || { upcoming: 0, live: 0 };
      row.live += 1; groups.set(match.competition, row);
    }
    renderApiLeagueRows(groups);

    const buckets = [["00-05", 0], ["06-11", 0], ["12-17", 0], ["18-23", 0]];
    for (const match of scheduled) {
      if (!match.time || Number.isNaN(match.time.valueOf())) continue;
      const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "America/Bogota", hour: "2-digit", hourCycle: "h23" }).format(match.time));
      const bucket = Math.min(3, Math.floor(hour / 6));
      buckets[bucket][1] += 1;
    }
    renderApiBarRows("#api-time-chart", buckets.map(([label, value]) => ({ label: `${label}:00`, value, kind: "api-upcoming-bar" })), "No hay próximos partidos.");

    const goals = new Map();
    for (const match of live) {
      const count = Number(match.home_score || 0) + Number(match.away_score || 0);
      goals.set(match.competition, (goals.get(match.competition) || 0) + count);
    }
    renderApiBarRows("#api-goals-chart", [...goals].map(([label, value]) => ({ label, value, kind: "api-live-bar" })).sort((a, b) => b.value - a.value).slice(0, 5), "No hay partidos en vivo en este momento.");
    status.textContent = scheduleResult.status === "fulfilled"
      ? `${scheduled.length} próximos | ${live.length} en vivo | datos de API-Football`
      : `${scheduled.length} próximos | ${live.length} en vivo | calendario: ${scheduleResult.reason?.message || "no disponible"}`;
  } catch (error) {
    status.textContent = error.message || "No se pudieron cargar los datos de la API.";
    renderApiLeagueRows(new Map());
    renderApiBarRows("#api-time-chart", [], "Datos no disponibles.");
    renderApiBarRows("#api-goals-chart", [], "Datos no disponibles.");
  }
}

async function loadAnalyticsLogos(matches) {
  const ids = [...new Set(matches.map((match) => fixtureLeagueId(match.competition)).filter((id) => id !== "other"))];
  await Promise.allSettled(ids.map(async (id) => {
    if (catalog[id]) return;
    const cached = getCachedCatalog(id);
    if (cached) { catalog[id] = cached; return; }
    const league = LEAGUES.find((item) => item.id === id);
    if (!league?.season) return;
    const response = await api(`/api/football/teams?league=${encodeURIComponent(id)}&season=${encodeURIComponent(league.season)}`);
    const teams = response.teams || [];
    catalog[id] = teams; saveCachedCatalog(id, teams);
  }));
}
function renderAnalyticsRanking() {
  const teams = analyticsData?.teams || [];
  if (!teams.length) { $("#analytics-team-ranking").innerHTML = `<p class="detail-unavailable">No hay métricas de equipos disponibles.</p>`; return; }
  $("#analytics-team-ranking").innerHTML = teams.slice(0, 6).map((team, index) => {
    const logo = analyticsTeamLogo(team.name);
    const form = (team.form || []).map((result) => `<i class="form-dot ${result === "W" ? "is-win" : result === "D" ? "is-draw" : "is-loss"}" title="${result === "W" ? "Victoria" : result === "D" ? "Empate" : "Derrota"}"></i>`).join("");
    return `<div class="ranking-row"><span class="ranking-position">${index + 1}.</span>${logo ? `<img src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="team-placeholder">${escapeHtml(team.name.slice(0,1))}</span>`}<div class="ranking-copy"><strong>${escapeHtml(team.name)}</strong><small>${escapeHtml(String(team.recent_win_rate ?? 0))}% victorias · últimos 5</small></div><div class="ranking-form" aria-label="Forma reciente">${form}</div></div>`;
  }).join("");
}
function renderAnalyticsGoals() {
  const teams = analyticsData?.teams || [];
  const max = Math.max(3, ...teams.map((team) => Number(team.goals_scored_avg) || 0));
  $("#analytics-goals-chart").innerHTML = teams.map((team) => {
    const scored = Math.max(4, (Number(team.goals_scored_avg) || 0) / max * 100);
    const conceded = Math.max(4, (Number(team.goals_conceded_avg) || 0) / max * 100);
    return `<div class="goal-row"><span class="goal-team">${escapeHtml(team.name.split(" ").slice(-1)[0])}</span><div class="goal-bars"><i class="goal-for" style="--bar:${scored}%" title="${team.goals_scored_avg} goles a favor"></i><i class="goal-against" style="--bar:${conceded}%" title="${team.goals_conceded_avg} goles en contra"></i></div><span class="goal-number">${escapeHtml(String(team.goals_scored_avg ?? "—"))}</span></div>`;
  }).join("");
}
function renderAnalyticsAttack(match) {
  if (!match) { $("#analytics-attack-metrics").innerHTML = `<p class="detail-unavailable">Selecciona un partido para ver su comparativa.</p>`; return; }
  const pairs = [[match.home, match.home_xg, match.home_corners], [match.away, match.away_xg, match.away_corners]];
  const xgMax = 3;
  $("#analytics-attack-metrics").innerHTML = `<div class="xg-pair">${pairs.map(([name, xg]) => {
    const amount = Number(xg) || 0, percentage = Math.min(100, Math.round(amount / xgMax * 100));
    const logo = analyticsTeamLogo(name);
    return `<div class="xg-item"><div class="xg-ring" style="--value:${percentage}%">${logo ? `<img src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<strong>${amount.toFixed(2)}</strong>`}</div><span>${escapeHtml(name)}</span><small>${amount.toFixed(2)} xG</small></div>`;
  }).join("")}</div><div class="corners-pair">${pairs.map(([name, , corners]) => `<div class="corner-stat"><span>${escapeHtml(name)}</span><strong>${escapeHtml(String(corners ?? "—"))}</strong><small>córners/partido</small></div>`).join("")}</div>`;
}
function renderAnalyticsH2H(match) {
  if (!match) { $("#analytics-h2h").innerHTML = `<p class="detail-unavailable">Selecciona un partido para consultar el historial.</p>`; return; }
  const btts = Number(match.h2h_btts_pct) || 0, over = Number(match.h2h_over_2_5_pct) || 0;
  const history = (match.h2h || []).map((result) => `<li>${escapeHtml(result)}</li>`).join("");
  $("#analytics-h2h").innerHTML = `<div class="h2h-circles"><div><div class="h2h-ring" style="--value:${btts}%"><strong>${btts}%</strong></div><span>Ambos marcan</span></div><div><div class="h2h-ring aqua" style="--value:${over}%"><strong>${over}%</strong></div><span>Más de 2.5</span></div></div><p class="h2h-average"><strong>${escapeHtml(String(match.h2h_goal_average ?? "—"))}</strong> goles promedio · últimos ${history ? (match.h2h || []).length : 0} duelos</p><details class="h2h-history"><summary>Ver resultados anteriores</summary><ul>${history || "<li>Sin resultados de H2H disponibles.</li>"}</ul></details>`;
}
function renderAnalyticsProbabilities(match) {
  if (!match) { $("#analytics-probabilities").innerHTML = `<p class="detail-unavailable">Selecciona un partido para ver la estimación derivada de las cuotas.</p>`; return; }
  const rows = [["1", match.home, match.probabilities?.home, "home"], ["X", "Empate", match.probabilities?.draw, "draw"], ["2", match.away, match.probabilities?.away, "away"]];
  $("#analytics-probabilities").innerHTML = `<div class="probability-list">${rows.map(([label, name, value, kind]) => `<div class="probability-row"><div class="probability-label"><span>${label}</span><strong>${escapeHtml(name)}</strong><b>${escapeHtml(String(value ?? "—"))}%</b></div><div class="probability-track"><i class="probability-fill ${kind}" style="--probability:${Number(value) || 0}%"></i></div></div>`).join("")}</div><p class="probability-disclaimer">Probabilidad implícita normalizada; no es una predicción garantizada.</p>`;
}
function renderAnalyticsRecommendations() {
  const matches = analyticsData?.matches || [];
  $("#analytics-recommendations").innerHTML = matches.length ? matches.map((match) => `<article class="analytics-recommendation"><div class="recommendation-comp">${escapeHtml(match.competition)}</div><h3>${escapeHtml(match.home)} vs ${escapeHtml(match.away)}</h3><p>${match.h2h_goal_average != null ? `El H2H de muestra promedia ${escapeHtml(String(match.h2h_goal_average))} goles en ${(match.h2h || []).length} encuentros.` : "Hay métricas recientes disponibles para ambos equipos."}</p><button type="button" data-analyze-match="${escapeHtml(match.id)}">Analizar partido <span>↗</span></button></article>`).join("") : `<p class="detail-unavailable">No hay partidos suficientes para generar comparativas.</p>`;
}
function renderAnalytics() {
  if (!analyticsData) return;
  const select = $("#analytics-match-select"), previous = selectedAnalyticsMatch;
  select.innerHTML = analyticsData.matches.map((match) => `<option value="${escapeHtml(match.id)}">${escapeHtml(match.home)} vs ${escapeHtml(match.away)}</option>`).join("");
  selectedAnalyticsMatch = analyticsData.matches.some((match) => match.id === previous) ? previous : analyticsData.matches[0]?.id || "";
  select.value = selectedAnalyticsMatch;
  const match = selectedAnalyticsFixture();
  $("#analytics-source-note").innerHTML = `<span>ⓘ</span><span>Selecciona una liga y dos equipos para consultar la comparación de temporada. Los gráficos de la derecha resumen los partidos reales disponibles.</span>`;
  $("#analytics-updated").textContent = `${analyticsData.matches.length} partidos · ${analyticsData.teams.length} equipos · muestra del ${escapeHtml(analyticsData.generated_at || "proyecto")}`;
  renderAnalyticsRanking(); renderAnalyticsGoals(); renderAnalyticsAttack(match); renderAnalyticsH2H(match); renderAnalyticsProbabilities(match); renderAnalyticsRecommendations();
}
function renderComparisonTeamOptions(teams, select, placeholder) {
  const previous = select.value;
  select.innerHTML = `<option value="">${placeholder}</option>${teams.map((team) => `<option value="${escapeHtml(String(team.id))}">${escapeHtml(team.name)}</option>`).join("")}`;
  if (teams.some((team) => String(team.id) === previous)) select.value = previous;
  select.disabled = !teams.length;
}
function comparisonTeamsForSelectedPot(excludeId = "") {
  const leagueId = $("#comparison-league")?.value;
  const pot = $("#comparison-group")?.value;
  return comparisonLeagueTeams.filter((team) =>
    (leagueId !== "2" || String(team.pot) === String(pot)) && String(team.id) !== String(excludeId)
  );
}
function configureComparisonGroup(leagueId) {
  const field = $("#comparison-group-field"), controls = $(".comparison-controls"), group = $("#comparison-group");
  if (!field || !group || !controls) return;
  const isChampions = leagueId === "2";
  field.hidden = !isChampions;
  controls.classList.toggle("is-champions", isChampions);
  if (isChampions) {
    const previous = group.value;
    group.innerHTML = [1, 2, 3, 4].map((pot) => `<option value="${pot}">Bombo ${pot}</option>`).join("");
    group.value = ["1", "2", "3", "4"].includes(previous) ? previous : "1";
  }
}
function applyComparisonPot() {
  const one = $("#comparison-team-one"), two = $("#comparison-team-two");
  if (!one || !two) return;
  const selectedOne = one.value;
  const teams = comparisonTeamsForSelectedPot();
  renderComparisonTeamOptions(teams, one, "Selecciona el equipo 1");
  if (selectedOne && teams.some((team) => team.id === selectedOne)) one.value = selectedOne;
  renderComparisonTeamOptions(comparisonTeamsForSelectedPot(one.value), two, "Selecciona el equipo 2");
  $("#comparison-status").textContent = `Bombo ${$("#comparison-group").value} · ${teams.length} equipos · elige dos para comparar.`;
  $("#comparison-results").innerHTML = `<p class="detail-unavailable">Elige dos equipos del mismo bombo para ver la comparación disponible.</p>`;
}
async function initTeamComparison() {
  const leagueSelect = $("#comparison-league");
  if (!leagueSelect) return;
  const current = leagueSelect.value;
  const comparisonLeagues = LEAGUES.filter((league) => league.id !== "143");
  leagueSelect.innerHTML = comparisonLeagues.map((league) => `<option value="${escapeHtml(league.id)}">${escapeHtml(league.name)}</option>`).join("");
  leagueSelect.value = comparisonLeagues.some((league) => league.id === current) ? current : selectedLeague.id;
  configureComparisonGroup(leagueSelect.value);
  await loadComparisonTeams(leagueSelect.value);
}
async function loadComparisonTeams(leagueId) {
  const league = LEAGUES.find((item) => item.id === leagueId);
  const one = $("#comparison-team-one"), two = $("#comparison-team-two");
  if (!league || !one || !two) return;
  configureComparisonGroup(leagueId);
  const token = ++comparisonRequestId;
  $("#comparison-status").textContent = `Cargando los equipos de ${league.name}…`;
  $("#comparison-results").innerHTML = `<p class="detail-unavailable">Elige los dos equipos para consultar sus estadísticas.</p>`;
  one.disabled = true; two.disabled = true;
  try {
    const cachedTeams = catalog[league.id]?.length ? catalog[league.id] : getCachedCatalog(league.id);
    const cachedTeamsHaveBadges = cachedTeams?.length && cachedTeams.every((team) => team.badge || team.logo);
    const data = cachedTeamsHaveBadges
      ? { teams: cachedTeams }
      : await api(`/api/football/teams?league=${encodeURIComponent(league.id)}&season=${encodeURIComponent(league.season)}`);
    if (token !== comparisonRequestId) return;
    comparisonLeagueTeams = (data.teams || []).map((team) => ({ ...team, id: String(team.id || team.team_id) })).filter((team) => team.id && team.name);
    catalog[league.id] = comparisonLeagueTeams;
    saveCachedCatalog(league.id, comparisonLeagueTeams);
    if (league.id === "2") {
      $("#comparison-group").value = "1";
      applyComparisonPot();
      $("#comparison-status").textContent = `${comparisonLeagueTeams.length} clasificados · 4 bombos oficiales de 9 equipos.`;
      return;
    }
    renderComparisonTeamOptions(comparisonLeagueTeams, one, "Selecciona el equipo 1");
    renderComparisonTeamOptions(comparisonLeagueTeams, two, "Selecciona el equipo 2");
    $("#comparison-status").textContent = comparisonLeagueTeams.length
      ? `${comparisonLeagueTeams.length} equipos disponibles · Temporada ${league.season}`
      : `No hay una plantilla disponible para ${league.name}.`;
  } catch (error) {
    if (token !== comparisonRequestId) return;
    comparisonLeagueTeams = [];
    renderComparisonTeamOptions([], one, "Equipos no disponibles");
    renderComparisonTeamOptions([], two, "Equipos no disponibles");
    $("#comparison-status").textContent = error.message || "No se pudieron cargar los equipos de la liga.";
  }
}
function renderTeamComparison(home, away) {
  const recentSample = String(home.source || "").includes("últimos") && String(away.source || "").includes("últimos");
  const stats = [
    ["Posición de liga", home.rank, away.rank],
    [recentSample ? "Puntos en la muestra" : "Puntos", recentSample ? home.sample_points : home.points, recentSample ? away.sample_points : away.points],
    [recentSample ? "Partidos en la muestra" : "Partidos jugados", home.played, away.played], ["Victorias", home.wins, away.wins],
    ["Goles a favor", home.goals_for, away.goals_for], ["Goles en contra", home.goals_against, away.goals_against],
    ["Promedio de goles a favor", home.goals_for_avg, away.goals_for_avg], ["Porterías a cero", home.clean_sheets, away.clean_sheets],
  ];  const teamCard = (team) => {
    const logo = safeImage(team.team?.logo);
    const fallbackLogo = safeImage(team.team?.fallback_logo);
    const name = String(team.team?.name || "Equipo");
    const form = team.form ? `<div class="comparison-form"><span>Forma reciente</span><b>${escapeHtml(team.form)}</b></div>` : "";
    const badge = logo
      ? `<img class="comparison-team-badge" src="${logo}" data-fallback="${fallbackLogo}" data-initial="${escapeHtml(name.slice(0,1))}" alt="Escudo de ${escapeHtml(name)}" loading="lazy" referrerpolicy="no-referrer">`
      : `<span class="team-placeholder">${escapeHtml(name.slice(0,1))}</span>`;
    return `<div class="comparison-team"><div class="comparison-team-identity">${badge}<strong>${escapeHtml(name)}</strong></div>${form}</div>`;
  };
  const availableStats = stats;
  const statRows = availableStats.map(([label, left, right]) => {
    const a = Number(left), b = Number(right), max = Math.max(a || 0, b || 0, 1);
    const value = (item) => item == null ? "—" : Number.isInteger(Number(item)) ? String(item) : Number(item).toFixed(2);
    return `<div class="comparison-stat-row"><span>${value(left)}</span><div><strong>${escapeHtml(label)}</strong><i><b style="--comparison-a:${Math.max(a ? 5 : 0, (a || 0) / max * 100)}%"></b><em style="--comparison-b:${Math.max(b ? 5 : 0, (b || 0) / max * 100)}%"></em></i></div><span>${value(right)}</span></div>`;
  }).join("");
  const hasStats = stats.some(([, left, right]) => left != null || right != null);
  const dataNote = recentSample
    ? `Forma reciente y resultados · ${escapeHtml(home.source)}`
    : hasStats
      ? `Temporada actual · fuente ${escapeHtml(home.source || away.source || "proveedor disponible")}`
    : "La comparación está lista, pero el proveedor no devolvió cifras verificables para esta temporada.";
  $("#comparison-results").innerHTML = `<div class="comparison-team-headings">${teamCard(home)}<span class="comparison-vs">VS</span>${teamCard(away)}</div><div class="comparison-stat-list"><div class="comparison-stat-labels"><span>${escapeHtml(home.team?.name || "Equipo 1")}</span><span>Estadística</span><span>${escapeHtml(away.team?.name || "Equipo 2")}</span></div>${statRows}</div><p class="comparison-data-note">${dataNote}</p>`;
}
async function compareSelectedTeams() {
  const league = LEAGUES.find((item) => item.id === $("#comparison-league").value);
  const homeId = $("#comparison-team-one").value, awayId = $("#comparison-team-two").value;
  if (!league || !homeId || !awayId || homeId === awayId) {
    $("#comparison-status").textContent = "Selecciona una liga y dos equipos diferentes para comparar.";
    return;
  }
  const token = ++comparisonRequestId;
  const button = $("#comparison-submit");
  button.disabled = true; button.textContent = "Consultando…";
  $("#comparison-status").textContent = "Consultando estadísticas oficiales de la temporada…";
  $("#comparison-results").innerHTML = `<p class="detail-unavailable">Cargando comparación…</p>`;
  const teamName = (id) => comparisonLeagueTeams.find((team) => team.id === id)?.name || "";
  const query = (id) => api(`/api/football/team-statistics?league=${encodeURIComponent(league.id)}&season=${encodeURIComponent(league.season)}&team=${encodeURIComponent(id)}&team_name=${encodeURIComponent(teamName(id))}`);
  try {
    const [homeStats, awayStats] = await Promise.all([query(homeId), query(awayId)]);
    if (token !== comparisonRequestId) return;
    const attachCatalogBadge = (stats, id) => {
      const catalogTeam = comparisonLeagueTeams.find((team) => team.id === String(id));
      const providerLogo = safeImage(stats.team?.logo);
      const catalogLogo = safeImage(catalogTeam?.badge || catalogTeam?.logo);
      const team = stats.team || {};
      return {
        ...stats,
        team: {
          ...team,
          id: String(id),
          name: team.name || catalogTeam?.name || teamName(id),
          logo: providerLogo || catalogLogo,
          fallback_logo: providerLogo && catalogLogo !== providerLogo ? catalogLogo : "",
        },
      };
    };
    const home = attachCatalogBadge(homeStats, homeId);
    const away = attachCatalogBadge(awayStats, awayId);
    renderTeamComparison(home, away);
    $("#comparison-status").textContent = `${league.name} · Temporada ${league.season}`;
  } catch (error) {
    if (token !== comparisonRequestId) return;
    $("#comparison-results").innerHTML = `<p class="detail-unavailable">${escapeHtml(error.message || "No se pudieron obtener las estadísticas comparativas.")}</p>`;
    $("#comparison-status").textContent = "No fue posible completar esta comparación.";
  } finally {
    if (token === comparisonRequestId) { button.disabled = false; button.textContent = "Comparar equipos"; }
  }
}
$("#comparison-league").addEventListener("change", (event) => loadComparisonTeams(event.target.value));
$("#comparison-group").addEventListener("change", applyComparisonPot);
$("#comparison-team-one").addEventListener("change", () => {
  const selected = $("#comparison-team-one").value;
  const two = $("#comparison-team-two"), previous = two.value;
  renderComparisonTeamOptions(comparisonTeamsForSelectedPot(selected), two, "Selecciona el equipo 2");
  if (comparisonLeagueTeams.some((team) => team.id === previous) && previous !== selected) two.value = previous;
});
$("#comparison-submit").addEventListener("click", compareSelectedTeams);
$("#analytics-refresh-teams").addEventListener("click", () => loadComparisonTeams($("#comparison-league").value));

async function loadAnalytics(force = false) {
  if (analyticsData && !force) { renderAnalytics(); return; }
  const button = $("#analytics-refresh"); button.classList.add("is-loading");
  try {
    analyticsData = await api("/api/analytics");
    await loadAnalyticsLogos(analyticsData.matches || []);
    renderAnalytics();
  } catch (error) {
    $("#analytics-source-note").innerHTML = `<span>!</span><span>${escapeHtml(error.message || "No se pudieron cargar las estadísticas.")}</span>`;
    $("#analytics-team-ranking").innerHTML = `<p class="detail-unavailable">No se pudo leer el dataset de estadísticas.</p>`;
  } finally { button.classList.remove("is-loading"); }
}
function analyzeAnalyticsMatch(id = selectedAnalyticsMatch) {
  const match = analyticsData?.matches.find((item) => item.id === id);
  if (!match) return;
  setView("home");
  const prompt = `Analiza el partido ${match.home} vs ${match.away} de ${match.competition}. Revisa forma, goles, xG, H2H y cuotas disponibles; aclara cuando los datos sean de demostración y no afirmes certezas.`;
  window.setTimeout(() => sendMessage(prompt), 120);
}
$("#analytics-match-select").addEventListener("change", (event) => {
  selectedAnalyticsMatch = event.target.value;
  const match = selectedAnalyticsFixture();
  renderAnalyticsAttack(match); renderAnalyticsH2H(match); renderAnalyticsProbabilities(match);
});
$("#analytics-refresh").addEventListener("click", () => loadAnalytics(true));
$("#api-charts-refresh").addEventListener("click", loadFootballCharts);
$("#analytics-chat-button").addEventListener("click", () => analyzeAnalyticsMatch());
$("#analytics-recommendations").addEventListener("click", (event) => {
  const button = event.target.closest("[data-analyze-match]");
  if (button) analyzeAnalyticsMatch(button.dataset.analyzeMatch);
});
function readProfileData() {
  try { return JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) || "{}"); }
  catch { return {}; }
}
function selectedValues(selector) { return [...document.querySelectorAll(selector)].filter((input) => input.checked).map((input) => input.value); }
function setProfileStatus(message, saved = false) {
  const status = $("#profile-save-status");
  status.textContent = message;
  status.classList.toggle("saved", saved);
}
function renderProfileAvatar(photo = localStorage.getItem(AVATAR_STORAGE_KEY)) {
  const host = $("#profile-avatar");
  host.replaceChildren();
  if (photo) {
    const image = document.createElement("img"); image.src = photo; image.alt = "Foto de perfil"; host.appendChild(image);
  } else {
    const initial = document.createElement("span"); initial.id = "profile-avatar-initial"; initial.textContent = $("#profile-name").value.trim().slice(0, 1).toLocaleUpperCase("es") || "U"; host.appendChild(initial);
  }
}
function renderProfileChoices() {
  $("#profile-league-choices").innerHTML = LEAGUES.map((league) => {
    const logo = safeImage(league.logo);
    const icon = logo ? `<img class="profile-choice-logo" src="${logo}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="profile-choice-flag">${escapeHtml(league.flag || "⚽")}</span>`;
    const countryName = countryLabel(league.country);
    return `<label class="profile-choice" data-search="${escapeHtml(`${league.name} ${league.country || ""} ${countryName}`.toLocaleLowerCase("es"))}"><input type="checkbox" value="${escapeHtml(league.id)}" data-profile-league><span class="profile-choice-check">&#10003;</span>${icon}<span>${escapeHtml(league.name)}${countryName ? ` · ${escapeHtml(countryName)}` : ""}</span></label>`;
  }).join("");
  $("#profile-country-choices").innerHTML = COUNTRIES.map((country) => {
    const flag = safeImage(country.flag);
    const icon = flag ? `<img class="profile-choice-logo country-flag" src="${flag}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="profile-choice-flag">🌍</span>`;
    return `<label class="profile-choice" data-search="${escapeHtml(`${country.name} ${country.id}`.toLocaleLowerCase("es"))}"><input type="checkbox" value="${escapeHtml(country.id)}" data-profile-country><span class="profile-choice-check">&#10003;</span>${icon}<span>${escapeHtml(country.name)}</span></label>`;
  }).join("");
}
function updateProfileSummary() {
  const leagueIds = selectedValues("[data-profile-league]"), countryIds = selectedValues("[data-profile-country]");
  const leagues = LEAGUES.filter((league) => leagueIds.includes(league.id));
  const countries = COUNTRIES.filter((country) => countryIds.includes(country.id));
  const value = LEAGUES.length ? Math.round(leagues.length / LEAGUES.length * 100) : 0;
  $("#profile-preference-donut").style.setProperty("--value", `${value}%`);
  $("#profile-preference-total").textContent = String(leagues.length);
  $("#profile-league-count").textContent = String(leagues.length);
  $("#profile-country-count").textContent = String(countries.length);
  $("#profile-summary-leagues").innerHTML = leagues.slice(0, 4).map((league) => `<li><i></i>${escapeHtml(league.name)}</li>`).join("") || `<li class="summary-empty">Aún no seleccionas ligas.</li>`;
  const filterItems = [];
  if (leagues.length) filterItems.push(`<li><span>•</span>Ligas priorizadas: ${leagues.map((league) => escapeHtml(league.name)).join(", ")}</li>`);
  if (countries.length) filterItems.push(`<li><span>•</span>Países favoritos: ${countries.map((country) => escapeHtml(country.name)).join(", ")}</li>`);
  $("#profile-active-filters").innerHTML = filterItems.join("") || `<li>Sin filtros favoritos seleccionados.</li>`;
  $("#profile-personalization-copy").textContent = leagues.length
    ? `La agenda priorizará tus ${leagues.length} ligas favoritas${countries.length ? ` y ${countries.length} países` : ""}.`
    : "Selecciona ligas para destacarlas en la agenda y en sus sugerencias rápidas.";
}
function renderProfile() {
  const profile = readProfileData();
  $("#profile-name").value = profile.name || "";
  $("#profile-email").value = profile.email || "";
  $("#profile-phone").value = profile.phone || "";
  renderProfileChoices();
  const leagues = new Set(favoriteLeagueIds);
  const countries = new Set(profile.countries || []);
  document.querySelectorAll("[data-profile-league]").forEach((input) => { input.checked = leagues.has(input.value); });
  document.querySelectorAll("[data-profile-country]").forEach((input) => { input.checked = countries.has(input.value); });
  renderProfileAvatar(); updateProfileSummary(); setProfileStatus("Cambios locales", true);
}
function saveProfile() {
  if (!$("#profile-form").reportValidity()) return;
  const profile = {
    name: $("#profile-name").value.trim(),
    email: $("#profile-email").value.trim(),
    phone: $("#profile-phone").value.trim(),
    countries: selectedValues("[data-profile-country]"),
  };
  favoriteLeagueIds = selectedValues("[data-profile-league]");
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  saveFavoriteLeagues();
  renderFavoriteLeagues(); updateProfileSummary();
  loadRecommendedTeams(favoriteLeagueIds);
  if (upcomingFixtures.length) renderUpcomingFixtures();
  setProfileStatus("Preferencias guardadas en este dispositivo", true);
}
function resetProfile() {
  localStorage.removeItem(PROFILE_STORAGE_KEY);
  localStorage.removeItem(AVATAR_STORAGE_KEY);
  favoriteLeagueIds = LEAGUES.some((league) => league.id === "39") ? ["39", "140"] : ["4328", "4335"];
  saveFavoriteLeagues();
  renderProfile(); renderFavoriteLeagues();
  loadRecommendedTeams(favoriteLeagueIds);
  if (upcomingFixtures.length) renderUpcomingFixtures();
  setProfileStatus("Preferencias restablecidas", true);
}
function markProfileChanged() { updateProfileSummary(); setProfileStatus("Tienes cambios sin guardar"); }
function handleProfilePhoto(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) { setProfileStatus("Elige un archivo de imagen"); return; }
  const objectUrl = URL.createObjectURL(file), image = new Image();
  image.onload = () => {
    const max = 512, scale = Math.min(1, max / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale)); canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff"; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(image, 0, 0, canvas.width, canvas.height);
    try {
      const compressed = canvas.toDataURL("image/jpeg", 0.82);
      localStorage.setItem(AVATAR_STORAGE_KEY, compressed); renderProfileAvatar(compressed); setProfileStatus("Foto guardada en este dispositivo", true);
    } catch { setProfileStatus("No se pudo guardar la imagen. Elige una más pequeña."); }
    URL.revokeObjectURL(objectUrl);
  };
  image.onerror = () => { URL.revokeObjectURL(objectUrl); setProfileStatus("No se pudo abrir esa imagen"); };
  image.src = objectUrl;
}
renderProfileChoices();
function filterProfileChoices(input, host) {
  const query = input.value.trim().toLocaleLowerCase("es");
  host.querySelectorAll(".profile-choice").forEach((choice) => { choice.hidden = !choice.dataset.search.includes(query); });
}
$("#profile-league-search").addEventListener("input", (event) => filterProfileChoices(event.target, $("#profile-league-choices")));
$("#profile-country-search").addEventListener("input", (event) => filterProfileChoices(event.target, $("#profile-country-choices")));
$("#profile-save").addEventListener("click", saveProfile);
$("#profile-reset").addEventListener("click", resetProfile);
$("#profile-form").addEventListener("submit", (event) => { event.preventDefault(); saveProfile(); });
$("#profile-form").addEventListener("input", markProfileChanged);
$("#profile-league-choices").addEventListener("change", () => { markProfileChanged(); loadRecommendedTeams(selectedValues("[data-profile-league]")); });
$("#profile-country-choices").addEventListener("change", markProfileChanged);
$("#profile-name").addEventListener("input", () => { if (!localStorage.getItem(AVATAR_STORAGE_KEY)) renderProfileAvatar(""); });
$("#profile-photo-input").addEventListener("change", (event) => handleProfilePhoto(event.target.files?.[0]));
$(".profile-tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-profile-tab]");
  if (!tab) return;
  const selected = tab.dataset.profileTab;
  document.querySelectorAll("[data-profile-tab]").forEach((button) => { const active = button === tab; button.classList.toggle("active", active); button.setAttribute("aria-selected", String(active)); });
  $("#profile-leagues-panel").hidden = selected !== "leagues";
  $("#profile-countries-panel").hidden = selected !== "countries";
});
function analyzeFixture(fixtureId) {
  const fixture = upcomingFixtures.find((match) => match.id === fixtureId);
  if (!fixture) return;
  const prompt = `Analiza el partido ${fixture.home} vs ${fixture.away} de ${fixture.competition}. Fecha y hora: ${fixtureLongDate(fixture)}. Usa únicamente los datos disponibles y señala si falta información.`;
  setView("home");
  window.setTimeout(() => sendMessage(prompt), 120);
}
renderFavoriteLeagues();
$("#fixture-selected-date").value = selectedFixtureDate;
$("#fixture-selected-date").addEventListener("change", (event) => {
  if (!event.target.value) return;
  selectedFixtureDate = event.target.value;
  localStorage.setItem("statstriker_selected_fixture_date", selectedFixtureDate);
  upcomingFixtures = [];
  loadUpcomingFixtures(true);
});
$("#fixture-today").addEventListener("click", () => {
  selectedFixtureDate = bogotaDate();
  $("#fixture-selected-date").value = selectedFixtureDate;
  localStorage.setItem("statstriker_selected_fixture_date", selectedFixtureDate);
  upcomingFixtures = [];
  $("#fixtures-grid").innerHTML = `<div class="live-empty"><span class="loader"></span><p>Cargando partidos de hoy…</p></div>`;
  loadUpcomingFixtures(true);
});
$("#fixture-search").addEventListener("input", renderUpcomingFixtures);
$("#fixture-sort").addEventListener("change", renderUpcomingFixtures);
$("#fixture-league-filter").addEventListener("change", renderUpcomingFixtures);
$("#fixture-refresh").addEventListener("click", () => loadUpcomingFixtures(true));
$("#favorite-leagues").addEventListener("change", (event) => {
  const input = event.target.closest("input[type=checkbox]");
  if (!input) return;
  favoriteLeagueIds = input.checked
    ? [...new Set([...favoriteLeagueIds, input.value])]
    : favoriteLeagueIds.filter((id) => id !== input.value);
  saveFavoriteLeagues(); renderFavoriteLeagues(); renderUpcomingFixtures(); loadRecommendedTeams(favoriteLeagueIds);
});
$("#recommended-teams-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-favorite-team]");
  if (!button) return;
  let team;
  try { team = JSON.parse(button.dataset.favoriteTeam); } catch { return; }
  const key = `${team.leagueId}:${team.id}`;
  favoriteTeams = favoriteTeams.some((item) => `${item.leagueId}:${item.id}` === key)
    ? favoriteTeams.filter((item) => `${item.leagueId}:${item.id}` !== key)
    : [...favoriteTeams, team];
  saveFavoriteTeams();
  renderRecommendedTeams(recommendedTeamGroups);
  loadMatches();
});
document.querySelectorAll("#fixtures-grid, #quick-analysis-list").forEach((host) => host.addEventListener("click", (event) => {
  const button = event.target.closest("[data-analyze-fixture]");
  if (button) analyzeFixture(button.dataset.analyzeFixture);
}));
document.addEventListener("error", (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.closest(".upcoming-view, .advanced-view, .profile-view, .league-list, #favorite-leagues")) return;
  const fallback = document.createElement("span"); fallback.className = "team-placeholder"; fallback.textContent = "⚽"; image.replaceWith(fallback);
}, true);

renderLeagues();
renderConversations();
lastFixtureContext = restoreFixtureContext(activeConversation()?.matchContext);
(async () => {
  await loadHealth();
  await syncBackendSessions();
  await loadHistory();
  await loadFootballLeagues();
  await initTeamComparison();
  if (!catalog[selectedLeague.id]) await loadLeague(selectedLeague.id);
  if (!recommendedTeamGroups.length) await loadMatches();
})();
