/* Painel de auditoria de prompts LLM — coordinator + PG + trading.
 * Sem dependências externas. Funciona em / e sob /llm-prompts/ (Authentik). */
(function () {
  "use strict";

  var TOGGLES = ["enabled", "log_controls", "log_window", "log_plan"];
  var NUMS = ["max_prompt_chars", "prune_days"];

  var $ = function (id) { return document.getElementById(id); };
  var apiKey = null;
  var offset = 0;
  var total = 0;
  var items = [];
  var selected = null;
  var dirty = false;
  var timer = null;

  // Base path: se estiver em /llm-prompts/, prefixa as APIs.
  function basePath() {
    var p = location.pathname || "/";
    if (p.indexOf("/llm-prompts") === 0) return "/llm-prompts";
    if (p.indexOf("/llm_prompts") === 0) return "/llm_prompts";
    if (p.indexOf("/llm-log") === 0) return "/llm-log";
    return "";
  }

  function apiUrl(path) {
    var base = basePath();
    var url = base + path;
    if (apiKey) {
      url += (url.indexOf("?") >= 0 ? "&" : "?") + "key=" + encodeURIComponent(apiKey);
    }
    return url;
  }

  function headers(json) {
    var h = {};
    if (json) h["Content-Type"] = "application/json";
    if (apiKey) h["X-API-KEY"] = apiKey;
    return h;
  }

  function setMsg(text, kind) {
    var m = $("msg");
    m.textContent = text || "";
    m.className = "msg" + (kind ? " " + kind : "");
  }

  function setCfgMsg(text, kind) {
    var m = $("cfgMsg");
    m.textContent = text || "";
    m.className = "msg" + (kind ? " " + kind : "");
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtTs(ts) {
    if (!ts) return "—";
    try {
      var d = new Date(ts);
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleString("pt-BR");
    } catch (e) {
      return String(ts);
    }
  }

  function queryParams() {
    return {
      source: $("source").value,
      q: $("q").value.trim(),
      model: $("model").value.trim(),
      status: $("status").value,
      limit: parseInt($("limit").value, 10) || 100,
      offset: offset
    };
  }

  function buildQuery(extra) {
    var p = queryParams();
    if (extra) Object.keys(extra).forEach(function (k) { p[k] = extra[k]; });
    var parts = [];
    Object.keys(p).forEach(function (k) {
      if (p[k] !== "" && p[k] != null) parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(p[k]));
    });
    return parts.join("&");
  }

  function renderStats(payload) {
    var box = $("stats");
    box.innerHTML = "";
    function mk(k, n) {
      var d = document.createElement("div");
      d.className = "stat";
      d.innerHTML = '<div class="n"></div><div class="k"></div>';
      d.querySelector(".n").textContent = Number(n || 0).toLocaleString("pt-BR");
      d.querySelector(".k").textContent = k;
      box.appendChild(d);
    }
    mk("total filtrado", payload.total);
    mk("nesta página", (payload.items || []).length);
    var bySrc = {};
    (payload.items || []).forEach(function (it) {
      bySrc[it.source] = (bySrc[it.source] || 0) + 1;
    });
    Object.keys(bySrc).forEach(function (s) { mk(s, bySrc[s]); });
  }

  function renderTable() {
    var wrap = $("tableWrap");
    if (!items.length) {
      wrap.innerHTML = '<div class="empty">Nenhum prompt encontrado com estes filtros.</div>';
      $("pageInfo").textContent = "0 itens";
      return;
    }
    var html = "<table><thead><tr>" +
      "<th>Quando</th><th>Fonte</th><th>Modelo</th><th>GPU</th><th>Status</th><th>s</th><th>Prompt</th>" +
      "</tr></thead><tbody>";
    items.forEach(function (it, idx) {
      var st = it.status;
      var stClass = (st >= 200 && st < 300) ? "ok" : "err";
      var prev = (it.prompt || "").replace(/\s+/g, " ").slice(0, 160);
      html += "<tr data-idx=\"" + idx + "\">" +
        "<td class=\"mono\">" + esc(fmtTs(it.ts)) + "</td>" +
        "<td><span class=\"chip\">" + esc(it.source) + "</span></td>" +
        "<td class=\"mono\">" + esc(it.model) + "</td>" +
        "<td class=\"mono\">" + esc(it.endpoint) + "</td>" +
        "<td><span class=\"chip " + stClass + "\">" + esc(st) + "</span></td>" +
        "<td class=\"mono\">" + esc(it.elapsed_s != null ? it.elapsed_s : "—") + "</td>" +
        "<td class=\"preview\" title=\"" + esc(prev) + "\">" + esc(prev) + "</td>" +
        "</tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;
    wrap.querySelectorAll("tr[data-idx]").forEach(function (tr) {
      tr.addEventListener("click", function () {
        var idx = parseInt(tr.getAttribute("data-idx"), 10);
        selectItem(items[idx], tr);
      });
    });
    var lim = parseInt($("limit").value, 10) || 100;
    $("pageInfo").textContent = (offset + 1) + "–" + Math.min(offset + lim, total) + " de " + total;
  }

  function selectItem(it, tr) {
    selected = it;
    $("detail").classList.add("open");
    document.querySelectorAll("tr.active").forEach(function (el) { el.classList.remove("active"); });
    if (tr) tr.classList.add("active");
    $("detailMeta").innerHTML =
      "<span class=\"chip\">" + esc(it.source) + "</span>" +
      "<span class=\"chip\">" + esc(it.model) + "</span>" +
      "<span class=\"chip\">" + esc(it.endpoint) + "</span>" +
      "<span class=\"chip\">" + esc(it.path) + "</span>" +
      "<span class=\"chip\">" + esc(it.status) + "</span>" +
      "<span class=\"chip\">" + esc(it.prompt_chars || (it.prompt || "").length) + " chars prompt</span>" +
      "<span class=\"chip\">" + esc(it.response_chars || (it.response || "").length) + " chars resposta</span>" +
      (it.error ? "<span class=\"chip err\">" + esc(it.error) + "</span>" : "") +
      "<div class=\"msg\" style=\"margin-top:6px\">" + esc(fmtTs(it.ts)) +
      (it.elapsed_s != null ? " · " + it.elapsed_s + "s" : "") + "</div>";
    $("detailPrompt").textContent = it.prompt || "(vazio)";
    $("detailResponse").textContent = it.response || it.error || "(sem resposta)";
    $("detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function loadPrompts() {
    setMsg("Carregando…", "");
    var url = apiUrl("/api/prompts?" + buildQuery());
    return fetch(url, { headers: headers(false) })
      .then(function (r) {
        if (r.status === 401) throw new Error("não autorizado (defina ?key= na URL ou X-API-KEY)");
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        items = data.items || [];
        total = data.total || 0;
        renderStats(data);
        renderTable();
        setMsg("Atualizado · fontes: " + (data.sources || []).join(", "), "ok");
      })
      .catch(function (e) {
        setMsg("Erro: " + e.message, "err");
        $("tableWrap").innerHTML = '<div class="empty">Falha ao carregar: ' + esc(e.message) + "</div>";
      });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return Promise.resolve();
  }

  function applyConfig(cfg) {
    if (!cfg) return;
    TOGGLES.forEach(function (k) { if (k in cfg && $(k)) $(k).checked = !!cfg[k]; });
    NUMS.forEach(function (k) { if (k in cfg && $(k)) $(k).value = cfg[k]; });
    if ("sample_rate" in cfg && $("sample_rate")) {
      $("sample_rate").value = cfg.sample_rate;
      $("sample_rate_val").textContent = Number(cfg.sample_rate).toFixed(2);
    }
    $("updated").textContent = cfg.updated_at
      ? ("Última alteração: " + cfg.updated_at + (cfg.updated_by ? " por " + cfg.updated_by : ""))
      : "";
  }

  function collectCfg() {
    var out = {};
    TOGGLES.forEach(function (k) { out[k] = $(k).checked; });
    NUMS.forEach(function (k) { out[k] = parseInt($(k).value, 10) || 0; });
    out.sample_rate = parseFloat($("sample_rate").value);
    return out;
  }

  function loadConfig() {
    return fetch(apiUrl("/api/config"), { headers: headers(false) })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (!data.available) {
          $("cfgMsg").textContent = "Config trading indisponível: " + (data.error || "sem DB");
          $("saveCfg").disabled = true;
          return;
        }
        applyConfig(data.config || {});
        dirty = false;
        $("saveCfg").disabled = true;
        setCfgMsg("Config carregada", "ok");
      })
      .catch(function () {});
  }

  function saveConfig() {
    $("saveCfg").disabled = true;
    setCfgMsg("Salvando…", "");
    fetch(apiUrl("/api/config"), {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(collectCfg())
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || ("HTTP " + r.status)); });
        return r.json();
      })
      .then(function (data) {
        applyConfig(data.config || {});
        dirty = false;
        setCfgMsg("Salvo ✓", "ok");
      })
      .catch(function (e) {
        setCfgMsg("Erro: " + e.message, "err");
        $("saveCfg").disabled = false;
      });
  }

  function markDirty() {
    dirty = true;
    $("saveCfg").disabled = false;
    setCfgMsg("Alterações não salvas", "");
  }

  function scheduleAuto() {
    if (timer) clearInterval(timer);
    timer = null;
    if ($("auto").checked) {
      timer = setInterval(function () { loadPrompts(); }, 10000);
    }
  }

  function init() {
    var m = /[?&]key=([^&]+)/.exec(location.search);
    if (m) apiKey = decodeURIComponent(m[1]);

    $("reload").addEventListener("click", function () { offset = 0; loadPrompts(); });
    $("exportBtn").addEventListener("click", function () {
      window.open(apiUrl("/api/prompts/export?" + buildQuery({ offset: 0, limit: 500 })), "_blank");
    });
    $("source").addEventListener("change", function () { offset = 0; loadPrompts(); });
    $("status").addEventListener("change", function () { offset = 0; loadPrompts(); });
    $("limit").addEventListener("change", function () { offset = 0; loadPrompts(); });
    $("q").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { offset = 0; loadPrompts(); }
    });
    $("model").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { offset = 0; loadPrompts(); }
    });
    $("prev").addEventListener("click", function () {
      var lim = parseInt($("limit").value, 10) || 100;
      offset = Math.max(0, offset - lim);
      loadPrompts();
    });
    $("next").addEventListener("click", function () {
      var lim = parseInt($("limit").value, 10) || 100;
      if (offset + lim < total) {
        offset += lim;
        loadPrompts();
      }
    });
    $("auto").addEventListener("change", scheduleAuto);

    $("copyPrompt").addEventListener("click", function () {
      if (!selected) return;
      copyText(selected.prompt || "").then(function () { setMsg("Prompt copiado", "ok"); });
    });
    $("copyResponse").addEventListener("click", function () {
      if (!selected) return;
      copyText(selected.response || "").then(function () { setMsg("Resposta copiada", "ok"); });
    });
    $("copyAll").addEventListener("click", function () {
      if (!selected) return;
      var blob = JSON.stringify(selected, null, 2);
      copyText(blob).then(function () { setMsg("JSON copiado", "ok"); });
    });

    TOGGLES.forEach(function (k) {
      if ($(k)) $(k).addEventListener("change", markDirty);
    });
    NUMS.forEach(function (k) {
      if ($(k)) $(k).addEventListener("input", markDirty);
    });
    if ($("sample_rate")) {
      $("sample_rate").addEventListener("input", function () {
        $("sample_rate_val").textContent = Number($("sample_rate").value).toFixed(2);
        markDirty();
      });
    }
    $("saveCfg").addEventListener("click", saveConfig);

    loadPrompts();
    loadConfig();
    scheduleAuto();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
