const STAGE_NAMES = ["New", "Learned", "Review 1", "Review 2", "Review 3", "Mastered"];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  currentUser: null,
  currentResult: null,
  currentBookWordId: null,
  studyQueue: [],
  studyIdx: 0,
  studyRevealed: false,
  authMode: "login", // or "register"
  suggestList: [],
  suggestIdx: -1,
};

// ---------- audio ----------
function playPronunciation(text, url) {
  if (url) {
    const audio = new Audio(url);
    audio.play().catch(() => fallbackTTS(text));
  } else {
    fallbackTTS(text);
  }
}
function fallbackTTS(text) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}
function audioBtn(text, url) {
  return `<button class="audio-btn" data-audio-text="${escapeHTML(text)}" data-audio-url="${escapeHTML(url || "")}" title="Play pronunciation" type="button">🔊</button>`;
}
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".audio-btn");
  if (!btn) return;
  e.preventDefault();
  e.stopPropagation();
  playPronunciation(btn.dataset.audioText || "", btn.dataset.audioUrl || "");
});

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// ---------- fetch ----------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...opts,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    if (res.status === 401) {
      state.currentUser = null;
      showAuthScreen();
    }
    const err = new Error((data && data.error) || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function escapeHTML(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---------- AUTH ----------
function showAuthScreen() {
  $("#app-root").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
  renderAuthMode();
  $("#auth-username").focus();
}

function showApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app-root").classList.remove("hidden");
  $("#user-name").textContent = state.currentUser.username;
  switchTab("search");
  loadBook().catch(() => {});
}

function renderAuthMode() {
  const isLogin = state.authMode === "login";
  $("#auth-sub").textContent = isLogin ? "Sign in to your account" : "Create a new account";
  $("#auth-submit").textContent = isLogin ? "Sign in" : "Create account";
  $("#auth-toggle-text").textContent = isLogin ? "New here?" : "Already have an account?";
  $("#auth-toggle-link").textContent = isLogin ? "Create an account" : "Sign in instead";
  $("#auth-password").autocomplete = isLogin ? "current-password" : "new-password";
  $("#auth-error").textContent = "";
}

$("#auth-toggle-link").addEventListener("click", (e) => {
  e.preventDefault();
  state.authMode = state.authMode === "login" ? "register" : "login";
  renderAuthMode();
});

$("#auth-submit").addEventListener("click", submitAuth);
$("#auth-password").addEventListener("keydown", (e) => { if (e.key === "Enter") submitAuth(); });
$("#auth-username").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#auth-password").focus(); });

async function submitAuth() {
  const username = $("#auth-username").value.trim();
  const password = $("#auth-password").value;
  const errEl = $("#auth-error");
  errEl.textContent = "";

  if (!username || !password) {
    errEl.textContent = "Username and password required.";
    return;
  }

  const endpoint = state.authMode === "login" ? "/api/login" : "/api/register";
  $("#auth-submit").disabled = true;
  try {
    const res = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    state.currentUser = res.user;
    $("#auth-password").value = "";
    showApp();
  } catch (e) {
    errEl.textContent = e.message || "Authentication failed.";
  } finally {
    $("#auth-submit").disabled = false;
  }
}

$("#logout-btn").addEventListener("click", async () => {
  try {
    await api("/api/logout", { method: "POST" });
  } catch {}
  state.currentUser = null;
  state.currentBookWordId = null;
  state.currentResult = null;
  $("#q").value = "";
  $("#search-result").innerHTML = "";
  $("#search-status").textContent = "";
  showAuthScreen();
});

// ---------- TABS ----------
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
function switchTab(tab) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $(`#view-${tab}`).classList.remove("hidden");
  if (tab === "book") loadBook();
}

// ---------- SEARCH ----------
$("#search-btn").addEventListener("click", () => { hideSuggest(); doSearch(); });
$("#q").addEventListener("keydown", (e) => {
  const box = $("#suggest-box");
  const visible = box && !box.classList.contains("hidden") && state.suggestList.length > 0;
  if (e.key === "ArrowDown" && visible) {
    e.preventDefault();
    state.suggestIdx = (state.suggestIdx + 1) % state.suggestList.length;
    renderSuggestHighlight();
    return;
  }
  if (e.key === "ArrowUp" && visible) {
    e.preventDefault();
    state.suggestIdx = state.suggestIdx <= 0 ? state.suggestList.length - 1 : state.suggestIdx - 1;
    renderSuggestHighlight();
    return;
  }
  if (e.key === "Escape") {
    hideSuggest();
    return;
  }
  if (e.key === "Enter") {
    if (visible && state.suggestIdx >= 0) {
      e.preventDefault();
      const word = state.suggestList[state.suggestIdx];
      $("#q").value = word;
      hideSuggest();
      doSearch();
      return;
    }
    hideSuggest();
    doSearch();
  }
});
$("#q").addEventListener("input", debounce(fetchSuggest, 180));
$("#q").addEventListener("blur", () => setTimeout(hideSuggest, 150));
$("#q").addEventListener("focus", () => {
  if (state.suggestList.length > 0) $("#suggest-box").classList.remove("hidden");
});

async function fetchSuggest() {
  const q = $("#q").value.trim();
  if (q.length < 2) {
    state.suggestList = [];
    hideSuggest();
    return;
  }
  let data;
  try {
    data = await api(`/api/suggest?q=${encodeURIComponent(q)}`);
  } catch {
    return;
  }
  state.suggestList = (data && data.suggestions) || [];
  state.suggestIdx = -1;
  renderSuggest();
}

function renderSuggest() {
  const box = $("#suggest-box");
  if (!box) return;
  if (state.suggestList.length === 0) {
    hideSuggest();
    return;
  }
  box.innerHTML = state.suggestList
    .map((w, i) => `<div class="suggest-item" data-idx="${i}">${escapeHTML(w)}</div>`)
    .join("");
  box.classList.remove("hidden");
  box.querySelectorAll(".suggest-item").forEach((el) => {
    el.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const word = state.suggestList[Number(el.dataset.idx)];
      $("#q").value = word;
      hideSuggest();
      doSearch();
    });
  });
}

function renderSuggestHighlight() {
  $$("#suggest-box .suggest-item").forEach((el, i) => {
    el.classList.toggle("highlight", i === state.suggestIdx);
  });
}

function hideSuggest() {
  const box = $("#suggest-box");
  if (box) box.classList.add("hidden");
  state.suggestIdx = -1;
}

async function doSearch() {
  const q = $("#q").value.trim();
  if (!q) return;
  setStatus("Looking up…");
  $("#search-result").innerHTML = "";
  $("#search-btn").disabled = true;
  hideSuggest();
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
    state.currentResult = data;
    renderSearchResult(data);
    setStatus("");
  } catch (e) {
    state.currentResult = null;
    if (e.status === 404) setStatus(`"${q}" not found.`, "error");
    else if (e.status === 401) setStatus("");
    else setStatus(e.message || "Lookup failed.", "error");
  } finally {
    $("#search-btn").disabled = false;
  }
}

function setStatus(msg, kind = "") {
  const el = $("#search-status");
  el.textContent = msg;
  el.className = "status" + (kind ? " " + kind : "");
}

function renderSearchResult(data) {
  const container = $("#search-result");
  const already = data.already_saved;
  const btnLabel = already ? "✓ Added" : "+ Add to My Book";
  const btnClass = already ? "btn secondary" : "btn primary";
  const disabled = already ? "disabled" : "";
  const imgTag = data.image_url
    ? `<img class="word-image" src="${escapeHTML(data.image_url)}" alt="${escapeHTML(data.word)}" onerror="this.remove()">`
    : "";

  container.innerHTML = `
    <div class="word-header">
      <div class="word-title">${escapeHTML(data.word)}</div>
      ${audioBtn(data.word, data.audio_url)}
      ${data.phonetic ? `<div class="phonetic">${escapeHTML(data.phonetic)}</div>` : ""}
      <button id="add-btn" class="${btnClass}" ${disabled}>${btnLabel}</button>
    </div>
    ${imgTag}
    <div id="defs-container"></div>
  `;

  const defsEl = $("#defs-container");
  data.definitions.forEach((d, i) => {
    const row = document.createElement("div");
    row.className = "def-row";
    row.innerHTML = `
      ${d.pos ? `<div class="def-pos">${escapeHTML(d.pos)}</div>` : ""}
      <div class="def-meaning">${i + 1}. ${escapeHTML(d.meaning)}</div>
      <div class="def-example-label">Example</div>
      <textarea class="def-example" data-idx="${i}" placeholder="Write your own example…">${escapeHTML(d.example || "")}</textarea>
    `;
    defsEl.appendChild(row);
  });

  if (!already) {
    $("#add-btn").addEventListener("click", addCurrent);
  }
}

async function addCurrent() {
  if (!state.currentResult) return;
  const defs = state.currentResult.definitions.map((d, i) => {
    const textarea = document.querySelector(`.def-example[data-idx="${i}"]`);
    return {
      pos: d.pos,
      meaning: d.meaning,
      example: textarea ? textarea.value.trim() : "",
    };
  });
  try {
    await api("/api/words", {
      method: "POST",
      body: JSON.stringify({
        word: state.currentResult.word,
        phonetic: state.currentResult.phonetic,
        image_url: state.currentResult.image_url || "",
        audio_url: state.currentResult.audio_url || "",
        definitions: defs,
      }),
    });
    const btn = $("#add-btn");
    btn.textContent = "✓ Added";
    btn.className = "btn secondary";
    btn.disabled = true;
    setStatus("Added to My Book.", "success");
  } catch (e) {
    setStatus(e.message || "Failed to add.", "error");
  }
}

// ---------- BOOK ----------
async function loadBook() {
  let words, counts;
  try {
    [words, counts] = await Promise.all([api("/api/words"), api("/api/counts")]);
  } catch (e) {
    if (e.status === 401) return;
    console.error(e);
    return;
  }
  $("#book-counts").textContent =
    `${counts.due} due today · ${counts.total} total · ${counts.mastered} mastered`;
  $("#start-btn").disabled = counts.due === 0;

  const list = $("#book-list");
  list.innerHTML = "";
  if (!words.length) {
    state.currentBookWordId = null;
    renderEmptyDetail();
    return;
  }
  words.forEach((w) => {
    const item = document.createElement("div");
    item.className = "book-item" + (state.currentBookWordId === w.id ? " selected" : "");
    item.innerHTML = `
      <div class="w">${escapeHTML(w.text)}</div>
      <div class="meta">
        <span class="stage-badge stage-${w.stage}">${STAGE_NAMES[w.stage]}</span>
        next: ${w.next_review_date}
      </div>
    `;
    item.addEventListener("click", () => {
      state.currentBookWordId = w.id;
      $$(".book-item").forEach((el) => el.classList.remove("selected"));
      item.classList.add("selected");
      showBookDetail(w.id);
    });
    list.appendChild(item);
  });

  if (state.currentBookWordId) showBookDetail(state.currentBookWordId);
  else renderEmptyDetail();
}

function renderEmptyDetail() {
  $("#book-detail").innerHTML =
    `<div class="muted centered">Select a word to view and edit its definitions.</div>`;
}

async function showBookDetail(wordId) {
  let data;
  try {
    data = await api(`/api/words/${wordId}`);
  } catch {
    renderEmptyDetail();
    return;
  }
  const p = data.progress || { stage: 0, next_review_date: "" };
  const imgTag = data.image_url
    ? `<img class="word-image" src="${escapeHTML(data.image_url)}" alt="${escapeHTML(data.text)}" onerror="this.remove()">`
    : "";
  $("#book-detail").innerHTML = `
    <div class="word-header">
      <div class="word-title">${escapeHTML(data.text)}</div>
      ${audioBtn(data.text, data.audio_url)}
      ${data.phonetic ? `<div class="phonetic">${escapeHTML(data.phonetic)}</div>` : ""}
      <button id="delete-btn" class="btn-ghost btn-danger">Remove from book</button>
    </div>
    ${imgTag}
    <div class="muted" style="margin-bottom:16px">
      <span class="stage-badge stage-${p.stage}">${STAGE_NAMES[p.stage]}</span>
      next review: ${p.next_review_date}
    </div>
    <div id="detail-defs"></div>
  `;

  $("#delete-btn").addEventListener("click", async () => {
    if (!confirm(`Remove "${data.text}" from your book?`)) return;
    try {
      await api(`/api/words/${wordId}`, { method: "DELETE" });
    } catch (e) {
      alert("Failed to delete: " + (e.message || e));
      return;
    }
    state.currentBookWordId = null;
    await loadBook();
  });

  const defsEl = $("#detail-defs");
  data.definitions.forEach((d, i) => {
    const row = document.createElement("div");
    row.className = "def-row";
    row.innerHTML = `
      ${d.part_of_speech ? `<div class="def-pos">${escapeHTML(d.part_of_speech)}</div>` : ""}
      <div class="def-meaning">${i + 1}. ${escapeHTML(d.meaning)}</div>
      <div class="def-example-label">Example (auto-saves on blur)</div>
      <textarea class="def-example" data-def-id="${d.id}" placeholder="Write your own example…">${escapeHTML(d.example || "")}</textarea>
    `;
    defsEl.appendChild(row);
    const ta = row.querySelector("textarea");
    ta.addEventListener("blur", async () => {
      try {
        await api(`/api/definitions/${d.id}`, {
          method: "PATCH",
          body: JSON.stringify({ example: ta.value.trim() }),
        });
      } catch (e) {
        console.error("save example failed", e);
      }
    });
  });
}

$("#start-btn").addEventListener("click", startStudy);

// ---------- STUDY ----------
async function startStudy() {
  const session = await api("/api/study/session");
  state.studyQueue = session;
  state.studyIdx = 0;
  state.studyRevealed = false;
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-study").classList.remove("hidden");
  showStudyCard();
}

$("#study-back").addEventListener("click", () => { switchTab("book"); });

function showStudyCard() {
  const total = state.studyQueue.length;
  const idx = state.studyIdx;
  const progressEl = $("#study-progress");
  const wordEl = $("#study-word");
  const phoneticEl = $("#study-phonetic");
  const defsEl = $("#study-defs");
  const actionsEl = $("#study-actions");

  if (idx >= total) {
    progressEl.textContent = "";
    wordEl.textContent = "All done for today! 🎉";
    $("#study-audio").innerHTML = "";
    phoneticEl.textContent = "";
    defsEl.innerHTML = `<div class="done">Come back tomorrow, or add more words to your book.</div>`;
    actionsEl.innerHTML = "";
    return;
  }

  const w = state.studyQueue[idx];
  state.studyRevealed = false;
  progressEl.textContent = `${idx + 1} / ${total}`;
  wordEl.textContent = w.text;
  $("#study-audio").innerHTML = audioBtn(w.text, w.audio_url);
  phoneticEl.textContent = w.phonetic || "";
  defsEl.innerHTML = "";

  actionsEl.innerHTML = `
    <button class="btn secondary dont" id="dont-btn">Don't know</button>
    <button class="btn secondary know" id="know-btn">Know</button>
  `;
  $("#dont-btn").addEventListener("click", () => answerStudy(false));
  $("#know-btn").addEventListener("click", () => answerStudy(true));

  playPronunciation(w.text, w.audio_url || "");
}

async function answerStudy(knew) {
  if (state.studyRevealed) return;
  const w = state.studyQueue[state.studyIdx];
  state.studyRevealed = true;

  try {
    await api("/api/answer", {
      method: "POST",
      body: JSON.stringify({ word_id: w.id, knew }),
    });
  } catch (e) {
    console.error("answer failed", e);
  }

  const defsEl = $("#study-defs");
  defsEl.innerHTML = "";
  if (w.image_url) {
    const img = document.createElement("img");
    img.className = "word-image";
    img.src = w.image_url;
    img.alt = w.text;
    img.onerror = () => img.remove();
    defsEl.appendChild(img);
  }
  w.definitions.forEach((d) => {
    const row = document.createElement("div");
    row.className = "def-row";
    let html = "";
    if (d.part_of_speech) html += `<div class="def-pos">${escapeHTML(d.part_of_speech)}</div>`;
    html += `<div class="def-meaning">${escapeHTML(d.meaning)}</div>`;
    if (d.example && d.example.trim())
      html += `<div class="def-block-example">“${escapeHTML(d.example.trim())}”</div>`;
    row.innerHTML = html;
    defsEl.appendChild(row);
  });

  $("#study-actions").innerHTML = `<button class="btn primary" id="next-btn">Next →</button>`;
  $("#next-btn").addEventListener("click", () => {
    state.studyIdx++;
    showStudyCard();
  });
}

// ---------- BOOTSTRAP ----------
(async function init() {
  try {
    const res = await fetch("/api/me", { credentials: "same-origin" });
    const data = await res.json();
    if (data.user) {
      state.currentUser = data.user;
      showApp();
    } else {
      showAuthScreen();
    }
  } catch {
    showAuthScreen();
  }
})();
