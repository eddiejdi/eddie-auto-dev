/* Painel da agenda diária — coleta, locução, Telegram e YouTube. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var apiKey = null;
  var selectedDate = null;
  var pollTimer = null;
  var promptDefaults = null;

  function headers() {
    var h = { "Content-Type": "application/json" };
    if (apiKey) h["X-API-KEY"] = apiKey;
    return h;
  }

  function setMsg(text, kind) {
    $("msg").textContent = text || "";
    $("msg").className = "msg" + (kind ? " " + kind : "");
  }

  function setPromptMsg(text, kind) {
    $("promptMsg").textContent = text || "";
    $("promptMsg").className = "msg" + (kind ? " " + kind : "");
  }

  function applyPrompts(prompts) {
    if (!prompts) return;
    $("prompt_expansion").value = prompts.expansion_template || "";
    $("prompt_broadcast").value = prompts.broadcast_template || "";
    if ($("prompt_editor")) {
      $("prompt_editor").value = prompts.editor_template || "";
    }
  }

  function savePrompts() {
    var expansion = $("prompt_expansion").value;
    var broadcast = $("prompt_broadcast").value;
    var editor = $("prompt_editor") ? $("prompt_editor").value : "";
    if (!expansion.trim() || !broadcast.trim()) {
      setPromptMsg("Os templates de expansão e locução são obrigatórios.", "err");
      return Promise.reject(new Error("prompts vazios"));
    }
    setPromptMsg("Salvando…", "");
    return fetch("/api/prompts", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        expansion_template: expansion,
        broadcast_template: broadcast,
        editor_template: editor,
      }),
    })
      .then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
          return j;
        });
      })
      .then(function (data) {
        applyPrompts(data.prompts);
        setPromptMsg("Prompts salvos — valem na próxima geração (sem redeploy).", "ok");
        return data;
      })
      .catch(function (e) {
        setPromptMsg("Erro: " + e.message, "err");
        throw e;
      });
  }

  function resetPrompts() {
    if (!promptDefaults) {
      setPromptMsg("Padrões ainda não carregados.", "err");
      return;
    }
    if (!confirm("Restaurar os templates padrão de fábrica?")) return;
    applyPrompts(promptDefaults);
    savePrompts();
  }

  function todayIso() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }

  function applyConfig(cfg) {
    $("youtube_enabled").checked = !!cfg.youtube.enabled;
    $("youtube_channel_id").value = cfg.youtube.channel_id || "";
    $("youtube_privacy").value = cfg.youtube.privacy_status || "public";
    $("run_mode").value = cfg.defaults.mode || "auto";
    $("run_quality").value = cfg.defaults.quality || "balanced";
    $("send_telegram").checked = cfg.defaults.send_telegram !== false;
    $("run_dry_run").checked = false;
    var audio = cfg.audio || {};
    if ($("min_audio_seconds")) {
      $("min_audio_seconds").value =
        audio.min_duration_seconds != null ? audio.min_duration_seconds : 3600;
    }
    if ($("segment_target_seconds")) {
      $("segment_target_seconds").value =
        audio.segment_target_seconds != null ? audio.segment_target_seconds : 180;
    }
    if ($("max_length_retries")) {
      $("max_length_retries").value =
        audio.max_length_retries != null ? audio.max_length_retries : 1;
    }
    if ($("editor_enabled")) {
      $("editor_enabled").checked = audio.editor_enabled !== false;
    }
    if (!$("run_date").value) $("run_date").value = todayIso();
  }

  function renderYoutubeStatus(yt) {
    var parts = [];
    if (yt.authenticated && !yt.channel_mismatch) {
      parts.push('<span class="badge ok">YouTube conectado</span> ');
      parts.push(yt.channel_title || yt.authenticated_channel_id || "Canal");
      if (yt.channel_url) {
        parts.push(' — <a href="' + yt.channel_url + '" target="_blank" rel="noopener">abrir canal</a>');
      }
    } else if (yt.channel_mismatch) {
      parts.push('<span class="badge err">Canal OAuth errado</span> ');
      parts.push("Publicaria em <strong>" + (yt.channel_title || yt.authenticated_channel_id) + "</strong>");
      parts.push(", mas o esperado é ");
      parts.push(yt.configured_channel_handle || yt.configured_channel_id || "@AgendaDiáriaImportante");
      parts.push(". Rode <code>python3 tools/setup_agenda_youtube_oauth.py --url-only</code> ");
      parts.push("com a conta Google do canal correto.");
    } else if (yt.upload_only_scope) {
      parts.push('<span class="badge err">Escopo insuficiente</span> ');
      parts.push("Token só permite upload, sem validar canal. ");
      parts.push("Reautentique sem <code>--upload-only-scope</code>.");
    } else if (yt.token_present && yt.credentials_present) {
      parts.push('<span class="badge err">Token inválido</span> ' + (yt.error || ""));
    } else {
      parts.push('<span class="badge err">OAuth pendente</span> ');
      parts.push("Coloque <code>credentials.json</code> em <code>artifacts/daily_agenda/youtube/</code> ");
      parts.push("e rode o fluxo OAuth na primeira publicação.");
    }
    $("ytStatus").innerHTML = parts.join("");
  }

  function renderEditions(editions) {
    var box = $("editions");
    box.innerHTML = "";
    if (!editions.length) {
      box.innerHTML = '<div class="hint">Nenhuma edição gerada ainda.</div>';
      return;
    }
    editions.forEach(function (ed) {
      var div = document.createElement("div");
      div.className = "edition" + (ed.date === selectedDate ? " active" : "");
      var badges = [];
      if (ed.has_wav) badges.push("áudio");
      if (ed.has_mp4) badges.push("mp4");
      if (ed.youtube_video_id) badges.push("YouTube");
      div.innerHTML =
        "<h3>" + ed.date + "</h3>" +
        '<div class="meta">' + badges.join(" · ") +
        (ed.youtube_url ? ' · <a href="' + ed.youtube_url + '" target="_blank" rel="noopener">vídeo</a>' : "") +
        "</div>" +
        '<button class="ghost" data-date="' + ed.date + '">Abrir</button>';
      div.querySelector("button").addEventListener("click", function () {
        openEdition(ed.date);
      });
      box.appendChild(div);
    });
  }

  var logOffset = 0;
  var logBuffer = "";
  var logStream = null; // EventSource
  var logPollTimer = null;
  var jobWasRunning = false;

  function setLiveIndicator(on, label) {
    var dot = $("jobLiveDot");
    var lab = $("jobLiveLabel");
    if (dot) {
      if (on) dot.classList.add("on");
      else dot.classList.remove("on");
    }
    if (lab) lab.textContent = label || (on ? "log ao vivo" : "log idle");
  }

  function appendJobLog(chunk, replace) {
    var el = $("jobLog");
    if (!el) return;
    if (replace) {
      logBuffer = chunk || "";
    } else if (chunk) {
      logBuffer += chunk;
      // limita buffer na UI (~400 KB)
      if (logBuffer.length > 400000) {
        logBuffer = logBuffer.slice(logBuffer.length - 350000);
        var cut = logBuffer.indexOf("\n");
        if (cut > 0) logBuffer = "…\n" + logBuffer.slice(cut + 1);
      }
    }
    if (!logBuffer) {
      el.textContent = "Aguardando job…";
      el.classList.add("empty");
      return;
    }
    el.classList.remove("empty");
    el.textContent = logBuffer;
    if ($("jobLogFollow") && $("jobLogFollow").checked) {
      el.scrollTop = el.scrollHeight;
    }
  }

  function updateJobLogMeta(info) {
    var el = $("jobLogMeta");
    if (!el) return;
    var parts = [];
    if (info && info.status) parts.push(info.status);
    if (info && info.phase) parts.push("fase " + info.phase);
    if (info && typeof info.size === "number") parts.push((info.size / 1024).toFixed(1) + " KB");
    if (info && typeof info.offset === "number") parts.push("offset " + info.offset);
    el.textContent = parts.join(" · ");
  }

  function stopLogStream() {
    if (logStream) {
      try { logStream.close(); } catch (e) {}
      logStream = null;
    }
    if (logPollTimer) {
      clearInterval(logPollTimer);
      logPollTimer = null;
    }
    setLiveIndicator(false, "log idle");
  }

  function startLogPolling() {
    if (logPollTimer) return;
    setLiveIndicator(true, "log ao vivo (poll)");
    logPollTimer = setInterval(function () {
      fetch("/api/job/log?since=" + logOffset, { headers: headers() })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data || !data.ok) return;
          if (data.chunk) {
            appendJobLog(data.chunk, false);
          }
          if (typeof data.offset === "number") logOffset = data.offset;
          updateJobLogMeta(data);
          if (data.done) {
            stopLogStream();
            // um último snapshot do job
            fetch("/api/job", { headers: headers() })
              .then(function (r) { return r.json(); })
              .then(function (j) { renderJob(j.job); })
              .catch(function () {});
          }
        })
        .catch(function () {});
    }, 1000);
  }

  function startLogStream() {
    stopLogStream();
    // SSE primeiro; se falhar (proxy/auth), cai no poll.
    if (typeof EventSource === "undefined") {
      startLogPolling();
      return;
    }
    var url = "/api/job/stream?since=" + logOffset;
    if (apiKey) url += (url.indexOf("?") >= 0 ? "&" : "?") + "key=" + encodeURIComponent(apiKey);
    try {
      // EventSource não envia headers custom; usa query key se o painel exige auth.
      logStream = new EventSource(url);
    } catch (e) {
      startLogPolling();
      return;
    }
    setLiveIndicator(true, "log ao vivo (SSE)");
    var gotAny = false;
    var failTimer = setTimeout(function () {
      if (!gotAny) {
        stopLogStream();
        startLogPolling();
      }
    }, 2500);
    logStream.addEventListener("hello", function () {
      gotAny = true;
      clearTimeout(failTimer);
    });
    logStream.addEventListener("log", function (ev) {
      gotAny = true;
      clearTimeout(failTimer);
      try {
        var data = JSON.parse(ev.data);
        if (data.chunk) appendJobLog(data.chunk, false);
        if (typeof data.offset === "number") logOffset = data.offset;
        updateJobLogMeta(data);
      } catch (e) {}
    });
    logStream.addEventListener("ping", function (ev) {
      gotAny = true;
      try {
        var data = JSON.parse(ev.data);
        updateJobLogMeta(data);
        if (data.done) {
          stopLogStream();
        }
      } catch (e) {}
    });
    logStream.addEventListener("done", function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.chunk) appendJobLog(data.chunk, false);
        if (typeof data.offset === "number") logOffset = data.offset;
        updateJobLogMeta(data);
      } catch (e) {}
      stopLogStream();
      fetch("/api/job", { headers: headers() })
        .then(function (r) { return r.json(); })
        .then(function (j) { renderJob(j.job); })
        .catch(function () {});
    });
    logStream.onerror = function () {
      // fallback silencioso para poll
      clearTimeout(failTimer);
      stopLogStream();
      startLogPolling();
    };
  }

  function renderJob(job) {
    if (!job || job.status === "idle") {
      $("jobStatus").textContent = "Nenhum job em execução.";
      $("runBtn").disabled = false;
      if ($("clearJobBtn")) $("clearJobBtn").disabled = false;
      if (jobWasRunning) {
        // mantém o log da última execução visível
        setLiveIndicator(false, "última execução");
      }
      jobWasRunning = false;
      stopLogStream();
      return;
    }
    var running = job.status === "running";
    $("runBtn").disabled = running;
    if ($("clearJobBtn")) $("clearJobBtn").disabled = false;
    var text = "Status: " + job.status;
    if (job.phase) text += " · fase: " + job.phase;
    if (job.date) text += " · data: " + job.date;
    if (job.pid) text += " · pid: " + job.pid;
    if (job.log_bytes) text += " · log " + (job.log_bytes / 1024).toFixed(1) + " KB";
    if (job.youtube && job.youtube.video_url) {
      text += ' · <a href="' + job.youtube.video_url + '" target="_blank" rel="noopener">YouTube</a>';
    }
    if (job.error) text += ' · <span class="badge err">' + job.error + "</span>";
    if (running) {
      text += ' · <span class="badge">log em tempo real</span>';
      text += ' · <span class="badge">se travar, use «Liberar botão»</span>';
    }
    $("jobStatus").innerHTML = text;

    // Snapshot do log embutido no job (fallback / catch-up).
    if (job.log && (!logBuffer || job.log.length > logBuffer.length)) {
      // só substitui se o snapshot for mais completo (início do job ou reentrada)
      if (!running || !logBuffer) {
        appendJobLog(job.log, true);
        if (typeof job.log_bytes === "number") logOffset = job.log_bytes;
      }
    }

    if (running) {
      if (!jobWasRunning) {
        // novo job: zera buffer se o log mudou de size/path
        if (!logBuffer) {
          logOffset = 0;
          appendJobLog("", true);
        }
        startLogStream();
      } else if (!logStream && !logPollTimer) {
        startLogStream();
      }
      jobWasRunning = true;
      setLiveIndicator(true, job.log_live ? "log ao vivo" : "log ao vivo…");
    } else {
      jobWasRunning = false;
      stopLogStream();
      if (job.log) appendJobLog(job.log, true);
      setLiveIndicator(false, job.status === "done" ? "concluído" : job.status);
    }
  }

  function clearJob() {
    setMsg("Liberando botão…", "");
    fetch("/api/job/clear", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ force: true }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || "falha ao limpar job");
        $("runBtn").disabled = false;
        renderJob(data.job || { status: "idle" });
        setMsg("Botão liberado — pode gerar de novo.", "ok");
      })
      .catch(function (e) {
        // fallback GET
        return fetch("/api/job/clear", { headers: headers() })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            $("runBtn").disabled = false;
            renderJob(data.job || { status: "idle" });
            setMsg("Botão liberado.", "ok");
          })
          .catch(function () {
            setMsg("Erro ao liberar: " + e.message, "err");
            $("runBtn").disabled = false;
          });
      });
  }

  function openEdition(dateStr) {
    selectedDate = dateStr;
    fetch("/api/editions/" + dateStr, { headers: headers() })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        $("previewText").value = data.locution || data.source || "";
        $("previewMeta").textContent = "Edição " + dateStr +
          (data.meta && data.meta.youtube_url ? " · publicada no YouTube" : "");
        var audio = $("previewAudio");
        if (data.has_wav) {
          audio.hidden = false;
          audio.src = "/api/editions/" + dateStr + "/audio?ts=" + Date.now();
        } else {
          audio.hidden = true;
          audio.removeAttribute("src");
        }
        $("uploadYtBtn").disabled = !data.has_wav;
        var link = $("youtubeLink");
        if (data.meta && data.meta.youtube_url) {
          link.href = data.meta.youtube_url;
          link.textContent = "Abrir no YouTube";
          link.hidden = false;
        } else {
          link.hidden = true;
        }
        return loadStatus();
      })
      .catch(function (e) { setMsg("Erro ao abrir edição: " + e.message, "err"); });
  }

  function collectConfigPatch() {
    var minAudio = parseInt($("min_audio_seconds").value, 10);
    var maxRetries = parseInt($("max_length_retries").value, 10);
    var segSec = parseInt($("segment_target_seconds") ? $("segment_target_seconds").value : "180", 10);
    if (isNaN(minAudio) || minAudio < 0) minAudio = 0;
    if (isNaN(maxRetries) || maxRetries < 0) maxRetries = 0;
    if (isNaN(segSec) || segSec < 90) segSec = 180;
    return {
      youtube: {
        enabled: $("youtube_enabled").checked,
        channel_id: $("youtube_channel_id").value.trim(),
        privacy_status: $("youtube_privacy").value,
      },
      defaults: {
        mode: $("run_mode").value,
        quality: $("run_quality").value,
        send_telegram: $("send_telegram").checked,
        upload_youtube: $("youtube_enabled").checked,
      },
      audio: {
        min_duration_seconds: minAudio,
        max_length_retries: maxRetries,
        segment_target_seconds: segSec,
        modular: minAudio >= 300,
        editor_enabled: $("editor_enabled") ? $("editor_enabled").checked : true,
      },
    };
  }

  function loadStatus() {
    return fetch("/api/status", { headers: headers() })
      .then(function (r) {
        if (r.status === 401) throw new Error("não autorizado (use ?key=... na URL)");
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        applyConfig(data.config);
        if (data.prompt_defaults) promptDefaults = data.prompt_defaults;
        applyPrompts(data.prompts || (data.config && data.config.prompts));
        renderYoutubeStatus(data.youtube);
        renderEditions(data.editions);
        renderJob(data.job);
        if (!selectedDate && data.editions.length) openEdition(data.editions[0].date);
        else if (selectedDate) {
          data.editions.forEach(function (ed) {
            if (ed.date === selectedDate) {
              var active = document.querySelector('.edition h3');
            }
          });
        }
      });
  }

  var saveConfigTimer = null;
  var saveConfigInFlight = null;

  function saveConfig() {
    // Serializa POSTs (evita corrida que truncava panel_config.json).
    var run = function () {
      return fetch("/api/config", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(collectConfigPatch()),
      }).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
          return j;
        });
      });
    };
    if (saveConfigInFlight) {
      saveConfigInFlight = saveConfigInFlight.then(run, run);
    } else {
      saveConfigInFlight = run();
    }
    return saveConfigInFlight.finally(function () {
      saveConfigInFlight = null;
    });
  }

  function scheduleSaveConfig() {
    if (saveConfigTimer) clearTimeout(saveConfigTimer);
    saveConfigTimer = setTimeout(function () {
      saveConfigTimer = null;
      saveConfig().catch(function (e) {
        setMsg("Config: " + e.message, "err");
      });
    }, 400);
  }

  function runJob() {
    $("runBtn").disabled = true;
    setMsg("Iniciando job…", "");
    // reseta log visual para o novo job
    logOffset = 0;
    logBuffer = "";
    jobWasRunning = false;
    appendJobLog("", true);
    stopLogStream();
    // Garante prompts + config salvos antes de gerar (sem redeploy).
    savePrompts()
      .then(function () { return saveConfig(); })
      .then(function () {
        return fetch("/api/run", {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({
            date: $("run_date").value || todayIso(),
            mode: $("run_mode").value,
            quality: $("run_quality").value,
            dry_run: $("run_dry_run").checked,
            send_telegram: $("send_telegram").checked,
            upload_youtube: $("youtube_enabled").checked,
          }),
        });
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || "falha ao iniciar job");
        setMsg("Job iniciado — log em tempo real abaixo", "ok");
        renderJob(data.job || { status: "running", phase: "broadcast" });
        pollJob();
        startLogStream();
      })
      .catch(function (e) {
        setMsg("Erro: " + e.message, "err");
        $("runBtn").disabled = false;
      });
  }

  function uploadYoutube() {
    if (!selectedDate) return;
    $("uploadYtBtn").disabled = true;
    setMsg("Publicando no YouTube…", "");
    saveConfig()
      .then(function () {
        return fetch("/api/youtube/upload", {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ date: selectedDate, privacy_status: $("youtube_privacy").value }),
        });
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        setMsg("Publicado: " + data.video_url, "ok");
        openEdition(selectedDate);
      })
      .catch(function (e) {
        setMsg("YouTube: " + e.message, "err");
        $("uploadYtBtn").disabled = false;
      });
  }

  function pollJob() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
      fetch("/api/job", { headers: headers() })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          renderJob(data.job);
          if (data.job.status !== "running") {
            clearInterval(pollTimer);
            pollTimer = null;
            stopLogStream();
            loadStatus().then(function () {
              if (data.job.date) openEdition(data.job.date);
            });
          }
        })
        .catch(function () {});
    }, 1500);
  }

  function init() {
    var m = /[?&]key=([^&]+)/.exec(location.search);
    if (m) apiKey = decodeURIComponent(m[1]);
    $("run_date").value = todayIso();
    $("runBtn").addEventListener("click", runJob);
    $("reloadBtn").addEventListener("click", function () { loadStatus().then(function () { setMsg("Recarregado", "ok"); }); });
    if ($("clearJobBtn")) $("clearJobBtn").addEventListener("click", clearJob);
    if ($("clearLogViewBtn")) {
      $("clearLogViewBtn").addEventListener("click", function () {
        logBuffer = "";
        appendJobLog("", true);
        setMsg("Tela do log limpa (arquivo do servidor preservado)", "ok");
      });
    }
    $("savePromptsBtn").addEventListener("click", function () {
      savePrompts().catch(function () {});
    });
    $("resetPromptsBtn").addEventListener("click", resetPrompts);
    $("uploadYtBtn").addEventListener("click", uploadYoutube);
    // Toggles/selects: salva no change. Números: debounce no input (evita corrida).
    ["youtube_enabled", "youtube_privacy", "run_mode", "run_quality", "send_telegram"]
      .forEach(function (id) {
        if (!$(id)) return;
        $(id).addEventListener("change", scheduleSaveConfig);
      });
    ["youtube_channel_id", "min_audio_seconds", "segment_target_seconds", "max_length_retries"].forEach(function (id) {
      if (!$(id)) return;
      $(id).addEventListener("input", scheduleSaveConfig);
      $(id).addEventListener("change", scheduleSaveConfig);
    });
    loadStatus()
      .then(function () {
        setMsg("Painel carregado", "ok");
        // se já houver job rodando ao abrir a página, liga o log ao vivo
        return fetch("/api/job", { headers: headers() }).then(function (r) { return r.json(); });
      })
      .then(function (data) {
        if (data && data.job) {
          renderJob(data.job);
          if (data.job.status === "running") {
            pollJob();
            startLogStream();
          } else if (data.job.log) {
            appendJobLog(data.job.log, true);
          }
        }
      })
      .catch(function (e) { setMsg("Erro ao carregar: " + e.message, "err"); });
    setInterval(function () {
      fetch("/api/job", { headers: headers() })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          renderJob(data.job);
          if (data.job && data.job.status === "running" && !logStream && !logPollTimer) {
            startLogStream();
          }
        })
        .catch(function () {});
    }, 5000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();