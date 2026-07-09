/* Painel da agenda diária — coleta, locução, Telegram e YouTube. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var apiKey = null;
  var selectedDate = null;
  var pollTimer = null;

  function headers() {
    var h = { "Content-Type": "application/json" };
    if (apiKey) h["X-API-KEY"] = apiKey;
    return h;
  }

  function setMsg(text, kind) {
    $("msg").textContent = text || "";
    $("msg").className = "msg" + (kind ? " " + kind : "");
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
    if (!$("run_date").value) $("run_date").value = todayIso();
  }

  function renderYoutubeStatus(yt) {
    var parts = [];
    if (yt.authenticated) {
      parts.push('<span class="badge ok">YouTube conectado</span> ');
      parts.push(yt.channel_title || yt.channel_id || "Canal");
      if (yt.channel_url) {
        parts.push(' — <a href="' + yt.channel_url + '" target="_blank" rel="noopener">abrir canal</a>');
      }
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

  function renderJob(job) {
    if (!job || job.status === "idle") {
      $("jobStatus").textContent = "Nenhum job em execução.";
      $("jobLog").hidden = true;
      $("runBtn").disabled = false;
      return;
    }
    $("runBtn").disabled = job.status === "running";
    var text = "Status: " + job.status;
    if (job.phase) text += " · fase: " + job.phase;
    if (job.date) text += " · data: " + job.date;
    if (job.youtube && job.youtube.video_url) {
      text += ' · <a href="' + job.youtube.video_url + '" target="_blank" rel="noopener">YouTube</a>';
    }
    if (job.error) text += ' · <span class="badge err">' + job.error + "</span>";
    $("jobStatus").innerHTML = text;
    if (job.log) {
      $("jobLog").hidden = false;
      $("jobLog").textContent = job.log;
    } else {
      $("jobLog").hidden = true;
    }
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

  function saveConfig() {
    return fetch("/api/config", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(collectConfigPatch()),
    }).then(function (r) { return r.ok ? r.json() : r.json().then(function (j) { throw new Error(j.error); }); });
  }

  function runJob() {
    $("runBtn").disabled = true;
    setMsg("Iniciando job…", "");
    saveConfig()
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
        setMsg("Job iniciado", "ok");
        pollJob();
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
            loadStatus().then(function () {
              if (data.job.date) openEdition(data.job.date);
            });
          }
        })
        .catch(function () {});
    }, 3000);
  }

  function init() {
    var m = /[?&]key=([^&]+)/.exec(location.search);
    if (m) apiKey = decodeURIComponent(m[1]);
    $("run_date").value = todayIso();
    $("runBtn").addEventListener("click", runJob);
    $("reloadBtn").addEventListener("click", function () { loadStatus().then(function () { setMsg("Recarregado", "ok"); }); });
    $("uploadYtBtn").addEventListener("click", uploadYoutube);
    ["youtube_enabled", "youtube_channel_id", "youtube_privacy", "run_mode", "run_quality", "send_telegram"]
      .forEach(function (id) {
        $(id).addEventListener("change", function () {
          saveConfig().catch(function (e) { setMsg("Config: " + e.message, "err"); });
        });
      });
    loadStatus()
      .then(function () { setMsg("Painel carregado", "ok"); })
      .catch(function (e) { setMsg("Erro ao carregar: " + e.message, "err"); });
    setInterval(function () {
      fetch("/api/job", { headers: headers() })
        .then(function (r) { return r.json(); })
        .then(function (data) { renderJob(data.job); })
        .catch(function () {});
    }, 10000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();