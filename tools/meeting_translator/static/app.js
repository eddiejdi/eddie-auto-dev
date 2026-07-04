// Tradutor de Reuniões — frontend
const $url = document.getElementById("url");
const $join = document.getElementById("join");
const $status = document.getElementById("status");

const STATE_LABEL = {
  iniciando: "iniciando",
  entrando: "entrando / aguardando admissão",
  na_reuniao: "na reunião ✅",
  erro: "erro",
  finalizado: "finalizado",
};

async function joinMeeting() {
  const url = $url.value.trim();
  if (!url) { $url.focus(); return; }
  $join.disabled = true;
  $join.textContent = "Entrando…";
  try {
    const r = await fetch("/api/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.statusText);
    $url.value = "";
  } catch (e) {
    alert("Não foi possível iniciar: " + e.message);
  } finally {
    $join.disabled = false;
    $join.textContent = "Entrar na reunião";
    refresh();
  }
}

async function refresh() {
  try {
    const r = await fetch("/api/jobs");
    const jobs = await r.json();
    $status.innerHTML = jobs.map(renderJob).join("");
  } catch { /* servidor reiniciando — tenta de novo no próximo tick */ }
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderJob(j) {
  const logItems = (j.log || []).slice(-8).map(
    (l) => `<li>[${esc(l.t)}] ${esc(l.msg)}</li>`
  ).join("");
  const platform = j.platform === "meet" ? "Google Meet" : "Microsoft Teams";
  return `
    <div class="job">
      <div class="head">
        <span>${platform} · ${esc(j.url).slice(0, 60)}…</span>
        <span class="state ${esc(j.state)}">${STATE_LABEL[j.state] || esc(j.state)}</span>
      </div>
      <ul class="log">${logItems}</ul>
    </div>`;
}

$join.addEventListener("click", joinMeeting);
$url.addEventListener("keydown", (e) => { if (e.key === "Enter") joinMeeting(); });
setInterval(refresh, 4000);
refresh();
