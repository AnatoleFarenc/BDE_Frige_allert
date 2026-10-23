// Dates use the browser locale; 2024-01-01 was a Monday, so weeks start on Monday.
const WEEKDAYS = Array.from({ length: 7 }, (_, i) =>
  new Date(2024, 0, 1 + i).toLocaleDateString(undefined, { weekday: "short" }));
const $ = (id) => document.getElementById(id);

let members = new Map();     // id -> {id, name, avatar}
let duties = {};             // "YYYY-MM-DD" -> [id, ...]
let viewMonth = startOfMonth(new Date());
let editing = null;          // { day, selected: Set }

function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
function iso(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function fromIso(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
function longDate(d) {
  return d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 401) { location.href = "/"; throw new Error("Not logged in"); }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
}

function chip(userId) {
  const m = members.get(userId) || { name: "Former member", avatar: "" };
  return el("div", { class: "chip", title: m.name },
    el("img", { class: "avatar", src: m.avatar, alt: "" }),
    el("span", {}, m.name));
}

function gridRange() {
  const first = viewMonth;
  const start = addDays(first, -((first.getDay() + 6) % 7));  // back to Monday
  return { start, end: addDays(start, 41) };
}

async function loadMonth() {
  const { start, end } = gridRange();
  duties = await api(`/api/duties?from=${iso(start)}&to=${iso(end)}`);
  renderCalendar();
}

function renderCalendar() {
  $("month-title").textContent = viewMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const cal = $("calendar");
  cal.replaceChildren(...WEEKDAYS.map((w) => el("div", { class: "weekday" }, w)));
  const { start } = gridRange();
  const today = iso(new Date());
  for (let i = 0; i < 42; i++) {
    const d = addDays(start, i);
    const key = iso(d);
    const classes = ["day"];
    if (d.getMonth() !== viewMonth.getMonth()) classes.push("other-month");
    if (d.getDay() === 5) classes.push("friday");
    if (key === today) classes.push("today");
    cal.append(el("button", { class: classes.join(" "), type: "button", onclick: () => openEditor(key) },
      el("span", { class: "num" }, String(d.getDate())),
      el("div", { class: "people" }, ...(duties[key] || []).map(chip))));
  }
}

async function loadUpcoming() {
  const today = new Date();
  const upcoming = await api(`/api/duties?from=${iso(today)}&to=${iso(addDays(today, 60))}`);
  const list = $("upcoming");
  const entries = Object.entries(upcoming).slice(0, 8);
  if (!entries.length) {
    list.replaceChildren(el("li", {}, "No duty scheduled. Click a day to add one."));
    return;
  }
  list.replaceChildren(...entries.map(([day, ids]) =>
    el("li", {}, el("span", { class: "date" }, longDate(fromIso(day))), ...ids.map(chip))));
}

function openEditor(day) {
  editing = { day, selected: new Set(duties[day] || []) };
  $("editor-title").textContent = longDate(fromIso(day));
  $("editor-notice").hidden = day !== iso(new Date());
  $("search").value = "";
  renderMemberList();
  $("editor").showModal();
}

function renderMemberList() {
  const query = $("search").value.trim().toLowerCase();
  const sorted = [...members.values()]
    .filter((m) => !query || m.name.toLowerCase().includes(query))
    .sort((a, b) => editing.selected.has(b.id) - editing.selected.has(a.id));
  $("member-list").replaceChildren(...sorted.map((m) => {
    const box = el("input", { type: "checkbox" });
    box.checked = editing.selected.has(m.id);
    box.addEventListener("change", () => {
      box.checked ? editing.selected.add(m.id) : editing.selected.delete(m.id);
      updateCount();
    });
    return el("label", {}, box, el("img", { class: "avatar lg", src: m.avatar, alt: "" }), m.name);
  }));
  updateCount();
}

function updateCount() {
  const n = editing.selected.size;
  $("count").textContent = n === 0 ? "Nobody" : `${n} selected`;
}

async function save(userIds) {
  $("save").disabled = true;
  try {
    await api(`/api/duties/${editing.day}`, { method: "PUT", body: JSON.stringify({ user_ids: userIds }) });
    $("editor").close();
    await Promise.all([loadMonth(), loadUpcoming()]);
  } catch (err) {
    alert(`Could not save: ${err.message}`);
  } finally {
    $("save").disabled = false;
  }
}

async function init() {
  const [me, list] = await Promise.all([api("/api/me"), api("/api/members")]);
  members = new Map(list.map((m) => [m.id, m]));
  $("me").replaceChildren(
    el("img", { class: "avatar lg", src: me.avatar, alt: "" }),
    el("span", {}, me.name),
    el("a", { href: "/logout" }, "Log out"));

  $("prev").onclick = () => { viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1); loadMonth(); };
  $("next").onclick = () => { viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 1); loadMonth(); };
  $("search").oninput = renderMemberList;
  $("cancel").onclick = () => $("editor").close();
  $("clear").onclick = () => save([]);
  $("editor-form").onsubmit = (e) => { e.preventDefault(); save([...editing.selected]); };

  await Promise.all([loadMonth(), loadUpcoming()]);
}

init();
