"use strict";
const $ = (id) => document.getElementById(id);
const S = {
  info: null, clips: [], sugg: [], sel: null, presets: {},
  t: { zoom: 100, volume: 20, mute: false, grain: 0, freeze: 0, quality: "crf", slug: "short" },
  endcard: false, logo: "",
};
const PRE = 5, POST = 15;                 // mark -> start = mark-5, end = mark+15
const OUT_W = 1080, OUT_H = 1920, SC = 0.3;
const SAFE = { top: 150, bottom: 400, right: 150 };
const RED = "#FF5A5F";
let nextId = 1;

// ---------- helpers ----------------------------------------------------------
async function api(url, body, method) {
  const opt = { method: method || (body === undefined ? "GET" : "POST"), headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, opt); } catch (e) { throw new Error("Can't reach the local server. Is app.py still running?"); }
  let data = {};
  try { data = await r.json(); } catch (e) { /* non-JSON */ }
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
function toast(msg, ok) {
  const t = $("toast"); t.textContent = msg; t.className = "toast" + (ok ? " ok" : ""); t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => (t.hidden = true), ok ? 3500 : 9000);
}
const fail = (e) => toast(e.message || String(e));
function fmtClock(s) {
  s = Math.max(0, s || 0); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = Math.floor(s % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`;
}
function fmtPrecise(s) {
  s = Math.max(0, s); const m = Math.floor(s / 60); return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`;
}
function parseTime(str) {
  str = String(str).trim(); if (!str) return NaN;
  const parts = str.split(":").map(Number); if (parts.some(isNaN)) return NaN;
  return parts.reduce((a, p) => a * 60 + p, 0);
}
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const video = $("video");
const dur = () => (S.info ? S.info.duration : 0);
const clip = () => S.clips.find((c) => c.id === S.sel);

// ---------- startup ----------------------------------------------------------
(async function init() {
  try {
    const st = await api("/api/status");
    if (!st.ok) { const b = $("banner"); b.textContent = st.message; b.hidden = false; }
    else if (!st.font) toast(st.font_warning);
    S.presets = await api("/api/presets"); renderPresets();
  } catch (e) { fail(e); }
  try { $("path").value = localStorage.getItem("dailyclip:lastpath") || ""; } catch (e) {}
})();

// ---------- load video -------------------------------------------------------
$("load").onclick = () => loadVideo($("path").value);
$("path").addEventListener("keydown", (e) => { if (e.key === "Enter") loadVideo($("path").value); });
$("pick").onclick = async () => {
  try { const r = await api("/api/pick", { kind: "video" }); if (r.path) { $("path").value = r.path; loadVideo(r.path); } }
  catch (e) { fail(e); }
};

async function loadVideo(path) {
  if (!path.trim()) return toast("Enter or pick a video file first.");
  $("load").disabled = true; $("info").textContent = "Reading file…";
  try {
    const info = await api("/api/load", { path });
    S.info = info; S.clips = []; S.sugg = []; S.sel = null;
    try { localStorage.setItem("dailyclip:lastpath", info.path); } catch (e) {}
    $("path").value = info.path;
    $("info").textContent = `${fmtClock(info.duration)} · ${info.width}×${info.height} · ${info.fps} fps · ${info.vcodec}` +
      (info.has_audio ? "" : " · no audio");
    restore(); $("app").hidden = false;
    video.src = "/media/video?v=" + Date.now();
    video.load();
    if (info.needs_proxy) startProxy("This format can't play in the browser — building a small 540p preview (exports still use the original)…");
    renderAll(); loadMissingThumbs();
  } catch (e) { $("info").textContent = ""; fail(e); }
  finally { $("load").disabled = false; }
}

let proxyStarted = false;
video.addEventListener("error", () => {
  if (S.info && !proxyStarted) startProxy("Browser can't play this file — building a 540p preview proxy…");
});
async function startProxy(msg) {
  proxyStarted = true;
  $("proxybar").hidden = false; $("proxymsg").textContent = msg; $("proxyfill").style.width = "0%";
  try {
    const { job } = await api("/api/proxy", {});
    await poll(job, (j) => ($("proxyfill").style.width = Math.round(j.progress * 100) + "%"));
    const t = video.currentTime; video.src = "/media/video?v=" + Date.now(); video.load();
    video.addEventListener("loadedmetadata", () => (video.currentTime = t), { once: true });
    $("proxymsg").textContent = "Preview proxy ready (preview only; export uses the original).";
    setTimeout(() => ($("proxybar").hidden = true), 4000);
  } catch (e) { $("proxybar").hidden = true; fail(e); }
  finally { proxyStarted = false; }
}

async function poll(job, onProgress) {
  for (;;) {
    const j = await api("/api/jobs/" + job);
    if (onProgress) onProgress(j);
    if (j.state === "done") return j.result;
    if (j.state === "error") throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 400));
  }
}

// ---------- persistence ------------------------------------------------------
const key = () => "dailyclip:project:" + (S.info ? S.info.key : "");
function persist() {
  if (!S.info) return;
  try { localStorage.setItem(key(), JSON.stringify({ clips: S.clips, t: S.t, endcard: S.endcard, logo: S.logo, nextId })); } catch (e) {}
}
function restore() {
  try {
    const d = JSON.parse(localStorage.getItem(key()) || "null"); if (!d) return;
    S.clips = (d.clips || []).filter((c) => c.end <= S.info.duration + 0.1);
    Object.assign(S.t, d.t || {}); S.endcard = !!d.endcard; S.logo = d.logo || ""; nextId = d.nextId || S.clips.length + 1;
    S.sel = S.clips.length ? S.clips[0].id : null;
  } catch (e) {}
}

// ---------- transport --------------------------------------------------------
$("play").onclick = () => (video.paused ? video.play() : video.pause());
video.addEventListener("play", () => ($("play").textContent = "⏸"));
video.addEventListener("pause", () => ($("play").textContent = "▶"));
video.addEventListener("click", () => $("play").click());
$("seek").addEventListener("input", () => { video.currentTime = ($("seek").value / 10000) * dur(); });
video.addEventListener("timeupdate", updateTime);
video.addEventListener("seeked", updateTime);
function updateTime() {
  if (!S.info) return;
  $("time").textContent = `${fmtClock(video.currentTime)} / ${fmtClock(dur())}`;
  if (document.activeElement !== $("seek")) $("seek").value = (video.currentTime / dur()) * 10000;
}
const seekBy = (d) => (video.currentTime = clamp(video.currentTime + d, 0, dur()));
$("back5").onclick = () => seekBy(-5); $("fwd5").onclick = () => seekBy(5);

document.addEventListener("keydown", (e) => {
  const t = e.target, tag = t.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT" || (tag === "INPUT" && t.type !== "range" && t.type !== "checkbox")) return;
  if (!S.info || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "m" || e.key === "M") { e.preventDefault(); addMark(); }
  else if (e.key === " ") { e.preventDefault(); $("play").click(); }
  else if (e.key === "ArrowLeft" && tag !== "INPUT") { e.preventDefault(); seekBy(e.shiftKey ? -1 : -5); }
  else if (e.key === "ArrowRight" && tag !== "INPUT") { e.preventDefault(); seekBy(e.shiftKey ? 1 : 5); }
});

// ---------- marks / clips ----------------------------------------------------
$("mark").onclick = addMark;
function addMark(at) {
  if (!S.info) return;
  const mark = typeof at === "number" ? at : video.currentTime;
  const c = { id: nextId++, mark, start: Math.max(0, mark - PRE), end: Math.min(dur(), mark + POST), thumb: null, texts: [] };
  if (c.end - c.start < 0.5) return toast("Too close to the end of the video to make a clip.");
  S.clips.push(c); S.clips.sort((a, b) => a.start - b.start); S.sel = c.id;
  fetchThumb(c, c.mark); renderAll(); persist();
  toast(`Marked ${fmtClock(mark)} → clip ${fmtPrecise(c.start)}–${fmtPrecise(c.end)}`, true);
}
async function fetchThumb(obj, t) {
  try { obj.thumb = (await api("/api/thumb", { t })).url; renderClips(); renderSuggs(); persist(); } catch (e) { /* ignore */ }
}
function loadMissingThumbs() { S.clips.forEach((c) => { if (!c.thumb) fetchThumb(c, c.mark); }); }

function renderClips() {
  const ul = $("clips"); ul.innerHTML = ""; $("clipcount").textContent = S.clips.length ? `(${S.clips.length})` : "";
  if (!S.clips.length) ul.innerHTML = '<li class="hint">No clips yet — press M at a moment.</li>';
  S.clips.forEach((c) => {
    const li = document.createElement("li"); li.className = "card" + (c.id === S.sel ? " sel" : "");
    li.innerHTML = `<img alt=""><div class="meta"><b>${fmtPrecise(c.start)} → ${fmtPrecise(c.end)}</b><span>mark ${fmtClock(c.mark)} · ${(c.end - c.start).toFixed(1)} s</span></div>`;
    if (c.thumb) li.querySelector("img").src = c.thumb;
    const del = document.createElement("button"); del.textContent = "✕"; del.title = "Delete clip";
    del.onclick = (e) => { e.stopPropagation(); S.clips = S.clips.filter((x) => x !== c); if (S.sel === c.id) S.sel = S.clips.length ? S.clips[0].id : null; renderAll(); persist(); };
    li.appendChild(del);
    li.onclick = () => { S.sel = c.id; video.currentTime = c.start; renderAll(); };
    ul.appendChild(li);
  });
}

// ---------- suggest moments --------------------------------------------------
$("suggest").onclick = async () => {
  if (!S.info) return;
  $("suggest").disabled = true; $("suggestprog").hidden = false; $("suggestfill").style.width = "0%";
  try {
    const { job } = await api("/api/suggest", { max: 30 });
    const res = await poll(job, (j) => ($("suggestfill").style.width = Math.round(j.progress * 100) + "%"));
    S.sugg = res.peaks; renderAll();
    toast(S.sugg.length ? `Found ${S.sugg.length} loud moments.` : "No loud peaks found.", true);
  } catch (e) { fail(e); }
  finally { $("suggest").disabled = false; $("suggestprog").hidden = true; }
};
function renderSuggs() {
  $("sugg").hidden = !S.sugg.length; $("suggcount").textContent = S.sugg.length ? `(${S.sugg.length})` : "";
  const ul = $("suggs"); ul.innerHTML = "";
  S.sugg.forEach((p) => {
    const li = document.createElement("li"); li.className = "card";
    li.innerHTML = `<img alt="" src="${p.thumb || ""}"><div class="meta"><b>${fmtClock(p.time)}</b><span>loudness</span><div class="energy"><div style="width:${Math.round(Math.sqrt(p.energy) * 100)}%"></div></div></div>`;
    const keep = document.createElement("button"); keep.textContent = "Keep";
    keep.onclick = (e) => { e.stopPropagation(); addMark(p.time); S.sugg = S.sugg.filter((x) => x !== p); renderAll(); };
    const skip = document.createElement("button"); skip.textContent = "✕"; skip.title = "Dismiss";
    skip.onclick = (e) => { e.stopPropagation(); S.sugg = S.sugg.filter((x) => x !== p); renderAll(); };
    li.append(keep, skip); li.onclick = () => { video.currentTime = Math.max(0, p.time - 2); }; ul.appendChild(li);
  });
}
function renderTicks() {
  const box = $("ticks"); box.innerHTML = ""; if (!S.info) return;
  const add = (t, cls) => { const d = document.createElement("div"); d.className = "tick " + cls; d.style.left = (t / dur()) * 100 + "%"; box.appendChild(d); };
  S.sugg.forEach((p) => add(p.time, "sug")); S.clips.forEach((c) => add(c.mark, c.id === S.sel ? "sel" : ""));
}

// ---------- selected clip editor --------------------------------------------
function renderEditor() {
  const c = clip(); $("noclip").hidden = !!c; $("editor").hidden = !c; if (!c) return;
  $("cstart").value = c.start.toFixed(2); $("cend").value = c.end.toFixed(2);
  updateDurLabel();
  $("zoom").value = S.t.zoom; $("zoomv").textContent = S.t.zoom + "%";
  $("volume").value = S.t.volume; $("volumev").textContent = S.t.volume + "%";
  $("mute").checked = S.t.mute; $("grain").value = S.t.grain; $("grainv").textContent = S.t.grain ? S.t.grain : "off";
  $("freeze").value = String(S.t.freeze); $("quality").value = S.t.quality; $("slug").value = S.t.slug;
  $("endcard").checked = S.endcard; $("logo").value = S.logo;
  renderTexts();
}
function updateDurLabel() {
  const c = clip(); if (!c) return;
  const bad = !(c.end > c.start);
  $("cdur").textContent = bad ? "⚠ End must be after start." : `Length ${(c.end - c.start).toFixed(2)} s` + (S.t.freeze ? ` + ${S.t.freeze} s freeze` : "") + (S.endcard ? " + 2.5 s end card" : "");
  $("cdur").style.color = bad ? "#ff8a8f" : "";
}
function bindTime(inputId, field) {
  $(inputId).addEventListener("change", () => {
    const c = clip(); const v = parseTime($(inputId).value);
    if (isNaN(v)) { toast("Enter a time like 83.5 or 1:23.5"); return renderEditor(); }
    c[field] = clamp(v, 0, dur()); renderClips(); updateDurLabel(); persist();
    if (!(c.end > c.start)) toast("End time must be after start time.");
  });
}
bindTime("cstart", "start"); bindTime("cend", "end");
$("setstart").onclick = () => { const c = clip(); c.start = video.currentTime; renderAll(); persist(); if (!(c.end > c.start)) toast("End time must be after start time."); };
$("setend").onclick = () => { const c = clip(); c.end = video.currentTime; renderAll(); persist(); if (!(c.end > c.start)) toast("End time must be after start time."); };

function bindSlider(id, outId, field, fmt) {
  $(id).addEventListener("input", () => { S.t[field] = Number($(id).value); $(outId).textContent = fmt(S.t[field]); updateDurLabel(); persist(); });
}
bindSlider("zoom", "zoomv", "zoom", (v) => v + "%");
bindSlider("volume", "volumev", "volume", (v) => v + "%");
bindSlider("grain", "grainv", "grain", (v) => (v ? v : "off"));
$("mute").onchange = () => { S.t.mute = $("mute").checked; persist(); };
$("freeze").onchange = () => { S.t.freeze = Number($("freeze").value); updateDurLabel(); persist(); };
$("quality").onchange = () => { S.t.quality = $("quality").value; persist(); };
$("slug").oninput = () => { S.t.slug = $("slug").value; persist(); };
$("endcard").onchange = () => { S.endcard = $("endcard").checked; updateDurLabel(); persist(); };
$("logo").oninput = () => { S.logo = $("logo").value; persist(); };
$("picklogo").onclick = async () => {
  try { const r = await api("/api/pick", { kind: "image" }); if (r.path) { $("logo").value = S.logo = r.path; $("endcard").checked = S.endcard = true; persist(); updateDurLabel(); } }
  catch (e) { fail(e); }
};

// ---------- text lines + presets --------------------------------------------
function renderPresets() {
  const sel = $("preset"); const cur = sel.value; sel.innerHTML = "";
  Object.keys(S.presets).forEach((n) => { const o = document.createElement("option"); o.textContent = n; sel.appendChild(o); });
  if (cur in S.presets) sel.value = cur;
}
const newLine = (o) => Object.assign({ text: "", size: 72, color: "white", x: null, y: 250, start: 0, end: null }, o || {});
$("addtext").onclick = () => { const c = clip(); c.texts.push(newLine({ text: "TEXT" })); renderTexts(); persist(); };
$("addpreset").onclick = () => {
  const c = clip(); const p = S.presets[$("preset").value]; if (!p) return;
  c.texts.push(newLine({ text: "YOUR TEXT", ...p })); renderTexts(); persist();
};
$("delpreset").onclick = async () => {
  const n = $("preset").value; if (!n || !confirm(`Delete preset "${n}"? (Built-in presets come back on restart.)`)) return;
  try { S.presets = await api("/api/presets/" + encodeURIComponent(n), undefined, "DELETE"); renderPresets(); } catch (e) { fail(e); }
};
function renderTexts() {
  const c = clip(); const box = $("texts"); box.innerHTML = ""; if (!c) return;
  c.texts.forEach((t, i) => {
    const d = document.createElement("div"); d.className = "textrow";
    d.innerHTML = `<textarea rows="1" placeholder="Text"></textarea>
      <div class="row">
        <label>Size <input data-k="size" type="number" min="12" max="300"></label>
        <select data-k="color"><option value="white">White</option><option value="red">Red #FF5A5F</option></select>
        <label>Start <input data-k="start" type="number" min="0" step="0.1"></label>
        <label>End <input data-k="end" type="number" min="0" step="0.1" placeholder="clip end"></label>
      </div>
      <div class="row">
        <label>Y <input data-k="y" type="number" step="10"></label>
        <label>X <input data-k="x" type="number" step="10" placeholder="center"></label>
        <button data-a="save" title="Save this style as a preset">Save as preset</button>
        <button data-a="del" title="Remove line">✕</button>
      </div>`;
    const ta = d.querySelector("textarea"); ta.value = t.text;
    ta.oninput = () => { t.text = ta.value; persist(); };
    d.querySelectorAll("[data-k]").forEach((el) => {
      const k = el.dataset.k; el.value = t[k] === null || t[k] === undefined ? "" : (k === "color" && t[k] === RED ? "red" : t[k]);
      el.oninput = el.onchange = () => {
        const v = el.value;
        t[k] = k === "color" ? v : v === "" ? (k === "end" || k === "x" ? null : t[k]) : Number(v); persist();
      };
    });
    d.querySelector('[data-a="del"]').onclick = () => { c.texts.splice(i, 1); renderTexts(); persist(); };
    d.querySelector('[data-a="save"]').onclick = async () => {
      const name = prompt("Preset name:", "My style"); if (!name) return;
      try { S.presets = await api("/api/presets", { name, style: { text: t.text, size: t.size, color: t.color, x: t.x, y: t.y, start: t.start, end: t.end } }); renderPresets(); $("preset").value = name; toast("Preset saved.", true); }
      catch (e) { fail(e); }
    };
    box.appendChild(d);
  });
}

// ---------- export -----------------------------------------------------------
$("export").onclick = async () => {
  const c = clip(); if (!c) return;
  if (!(c.end > c.start)) return toast("End time must be after start time.");
  if (S.endcard && !S.logo.trim()) return toast("Choose a logo image for the end card, or untick it.");
  $("export").disabled = true; $("result").hidden = true; $("exportprog").hidden = false;
  $("exportfill").style.width = "0%"; $("exportmsg").textContent = "Exporting…";
  const body = {
    start: c.start, end: c.end, zoom: S.t.zoom / 100, volume: S.t.volume / 100, mute: S.t.mute,
    grain: S.t.grain, freeze: S.t.freeze, quality: S.t.quality, slug: S.t.slug,
    endcard_logo: S.endcard ? S.logo : null,
    texts: c.texts.map((t) => ({ ...t, color: t.color === "red" ? RED : t.color })),
  };
  try {
    const { job } = await api("/api/export", body);
    const res = await poll(job, (j) => { const p = Math.round(j.progress * 100); $("exportfill").style.width = p + "%"; $("exportmsg").textContent = `Exporting… ${p}%`; });
    $("exportmsg").textContent = "Done."; $("result").hidden = false;
    $("resname").textContent = res.file; $("respath").textContent = res.path; $("reslink").href = res.url;
    if (res.contact_sheet) { $("sheet").src = res.contact_sheet + "?t=" + Date.now(); $("sheetlink").href = res.contact_sheet; }
    toast("Export finished: " + res.file, true);
  } catch (e) { $("exportmsg").textContent = "Failed."; fail(e); }
  finally { $("export").disabled = false; }
};

// ---------- 9:16 live preview -----------------------------------------------
const cv = $("short"), ctx = cv.getContext("2d");
function drawPreview() {
  const W = cv.width, H = cv.height;
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
  const vw = video.videoWidth, vh = video.videoHeight;
  if (vw && vh) {
    // background: fill + blur + darken
    const s = Math.max(W / vw, H / vh);
    ctx.save(); ctx.filter = "blur(9px) brightness(0.85)";
    ctx.drawImage(video, (W - vw * s) / 2, (H - vh * s) / 2, vw * s, vh * s); ctx.restore();
    // foreground: 1080 wide x zoom, centered, sides cropped by canvas
    const z = S.t.zoom / 100, fw = W * z, fh = vh * (fw / vw);
    ctx.drawImage(video, (W - fw) / 2, (H - fh) / 2, fw, fh);
  }
  const c = clip();
  if (c) {
    const rel = video.currentTime - c.start, all = $("alltext").checked;
    c.texts.forEach((t) => {
      const end = t.end === null || t.end === undefined ? c.end - c.start : t.end;
      if (!all && !(rel >= t.start && rel <= end)) return;
      const lines = (t.text || "").split("\n").filter((l) => l.trim());
      ctx.font = `700 ${t.size * SC}px Poppins, Arial, sans-serif`; ctx.textBaseline = "top";
      ctx.lineJoin = "round"; ctx.lineWidth = Math.max(3, Math.round(t.size * 0.09)) * 2 * SC;
      lines.forEach((ln, j) => {
        const w = ctx.measureText(ln).width, x = t.x === null || t.x === undefined ? (W - w) / 2 : t.x * SC;
        const y = (t.y + j * Math.round(t.size * 1.3)) * SC;
        ctx.strokeStyle = "#000"; ctx.strokeText(ln, x, y);
        ctx.fillStyle = t.color === "red" ? RED : t.color === "white" ? "#fff" : t.color; ctx.fillText(ln, x, y);
      });
    });
  }
  if ($("safe").checked) {
    ctx.fillStyle = "rgba(255,40,60,0.22)";
    ctx.fillRect(0, 0, W, SAFE.top * SC);
    ctx.fillRect(0, H - SAFE.bottom * SC, W, SAFE.bottom * SC);
    ctx.fillRect(W - SAFE.right * SC, SAFE.top * SC, SAFE.right * SC, H - (SAFE.top + SAFE.bottom) * SC);
    ctx.strokeStyle = "rgba(255,90,95,0.9)"; ctx.setLineDash([5, 4]); ctx.lineWidth = 1;
    ctx.strokeRect(0.5, SAFE.top * SC, W - SAFE.right * SC, H - (SAFE.top + SAFE.bottom) * SC); ctx.setLineDash([]);
  }
  requestAnimationFrame(drawPreview);
}
requestAnimationFrame(drawPreview);

function renderAll() { renderClips(); renderSuggs(); renderTicks(); renderEditor(); updateTime(); }
