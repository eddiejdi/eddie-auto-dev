/* Painel de controle do log de LLM (Fase 1 do fine-tuning trading-analyst).
 * Lê/grava btc.llm_log_config via /api/config e mostra stats de btc.llm_calls.
 * Sem dependências externas (CSP-friendly). */
(function () {
  "use strict";

  var TOGGLES = ["enabled", "log_controls", "log_window", "log_plan"];
  var NUMS = ["max_prompt_chars", "prune_days"];
  var CALL_TYPES = ["controls", "window", "plan"];

  var $ = function (id) { return document.getElementById(id); };
  var dirty = false;
  var apiKey = null; // preenchido via ?key= na URL, se houver

  function headers() {
    var h = { "Content-Type": "application/json" };
    if (apiKey) h["X-API-KEY"] = apiKey;
    return h;
  }

  function setMsg(text, kind) {
    var m = $("msg");
    m.textContent = text || "";
    m.className = "msg" + (kind ? " " + kind : "");
  }

  function markDirty() {
    dirty = true;
    $("save").disabled = false;
    setMsg("Alterações não salvas", "");
  }

  function applyConfig(cfg) {
    TOGGLES.forEach(function (k) { if (k in cfg) $(k).checked = !!cfg[k]; });
    NUMS.forEach(function (k) { if (k in cfg) $(k).value = cfg[k]; });
    if ("sample_rate" in cfg) {
      $("sample_rate").value = cfg.sample_rate;
      $("sample_rate_val").textContent = Number(cfg.sample_rate).toFixed(2);
    }
    reflectEnabled();
    $("updated").textContent = cfg.updated_at
      ? ("Última alteração: " + cfg.updated_at + (cfg.updated_by ? " por " + cfg.updated_by : ""))
      : "Sem alterações registradas.";
  }

  function reflectEnabled() {
    var on = $("enabled").checked;
    var st = $("enabledState");
    st.textContent = on ? "Ativado" : "Desativado";
    st.className = "state " + (on ? "on" : "off");
    // Parâmetros ficam esmaecidos (mas editáveis) quando o log está off.
    $("paramsCard").classList.toggle("dim", !on);
  }

  function collect() {
    var out = {};
    TOGGLES.forEach(function (k) { out[k] = $(k).checked; });
    NUMS.forEach(function (k) { out[k] = parseInt($(k).value, 10) || 0; });
    out.sample_rate = parseFloat($("sample_rate").value);
    return out;
  }

  function renderStats(stats) {
    var box = $("stats");
    box.innerHTML = "";
    var mk = function (k, n) {
      var d = document.createElement("div");
      d.className = "stat";
      d.innerHTML = '<div class="n"></div><div class="k"></div>';
      d.querySelector(".n").textContent = Number(n || 0).toLocaleString("pt-BR");
      d.querySelector(".k").textContent = k;
      box.appendChild(d);
    };
    mk("total", stats.total);
    CALL_TYPES.forEach(function (ct) {
      var s = (stats.by_type && stats.by_type[ct]) || { total: 0, last_24h: 0 };
      mk(ct + " (24h)", s.last_24h);
    });
    $("statsFoot").textContent = stats.last_ts
      ? "Última chamada logada: " + new Date(stats.last_ts * 1000).toLocaleString("pt-BR")
      : "Nenhuma chamada logada ainda (esperado até a Fase 1 rodar em produção).";
  }

  function load() {
    return fetch("/api/config", { headers: headers() })
      .then(function (r) {
        if (r.status === 401) throw new Error("não autorizado (defina ?key=... na URL)");
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        applyConfig(data.config);
        renderStats(data.stats);
        dirty = false;
        $("save").disabled = true;
        setMsg("Carregado", "ok");
      })
      .catch(function (e) { setMsg("Erro ao carregar: " + e.message, "err"); });
  }

  function save() {
    $("save").disabled = true;
    setMsg("Salvando…", "");
    fetch("/api/config", { method: "POST", headers: headers(), body: JSON.stringify(collect()) })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || ("HTTP " + r.status)); });
        return r.json();
      })
      .then(function (data) {
        applyConfig(data.config);
        renderStats(data.stats);
        dirty = false;
        setMsg("Salvo ✓", "ok");
      })
      .catch(function (e) { setMsg("Erro ao salvar: " + e.message, "err"); $("save").disabled = false; });
  }

  function refreshStats() {
    fetch("/api/config", { headers: headers() })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) renderStats(data.stats); })
      .catch(function () {});
  }

  function init() {
    var m = /[?&]key=([^&]+)/.exec(location.search);
    if (m) apiKey = decodeURIComponent(m[1]);

    TOGGLES.forEach(function (k) {
      $(k).addEventListener("change", function () {
        if (k === "enabled") reflectEnabled();
        markDirty();
      });
    });
    NUMS.forEach(function (k) { $(k).addEventListener("input", markDirty); });
    $("sample_rate").addEventListener("input", function () {
      $("sample_rate_val").textContent = Number($("sample_rate").value).toFixed(2);
      markDirty();
    });
    $("save").addEventListener("click", save);
    $("reload").addEventListener("click", function () {
      if (dirty && !confirm("Descartar alterações não salvas?")) return;
      load();
    });
    window.addEventListener("beforeunload", function (e) {
      if (dirty) { e.preventDefault(); e.returnValue = ""; }
    });

    load();
    // Stats ao vivo (não sobrescreve edições em andamento).
    setInterval(function () { if (!dirty) refreshStats(); }, 10000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
