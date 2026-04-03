const api = typeof browser !== 'undefined' ? browser : chrome;

const DEFAULT_SETTINGS = {
  rpa4allApiBaseUrl: 'https://api.rpa4all.com/agents-api',
  rpa4allMassesPath: '/marketing/profile',
  rpa4allAuthToken: '',
  rpa4allDefaultQuery: '',
  rpa4allAutoRefreshEnabled: true,
  rpa4allAutoRefreshMinutes: 30
};

// ── Auto-update constants ──────────────────────────────────────────────────
const LATEST_JSON_URL = 'https://www.rpa4all.com/extension-updates/latest.json';
const UPDATE_CHECK_ALARM = 'rpa4all-update-check';
const UPDATE_CHECK_INTERVAL_MINUTES = 60; // verificar a cada hora
const CURRENT_VERSION = api.runtime.getManifest().version;

const AUTO_REFRESH_ALARM = 'rpa4all-auto-refresh';

// ── Version comparison helper ─────────────────────────────────────────────
function isNewerVersion(remote, current) {
  const parse = (v) => String(v || '0').split('.').map(Number);
  const r = parse(remote);
  const c = parse(current);
  const len = Math.max(r.length, c.length);
  for (let i = 0; i < len; i++) {
    const rv = r[i] || 0;
    const cv = c[i] || 0;
    if (rv > cv) { return true; }
    if (rv < cv) { return false; }
  }
  return false;
}

// ── Auto-update: check remote latest.json ────────────────────────────────
async function checkForUpdate() {
  try {
    const resp = await fetch(LATEST_JSON_URL, { cache: 'no-store' });
    if (!resp.ok) { return; }
    const data = await resp.json();
    const remoteVersion = String(data.version || '');
    if (!remoteVersion) { return; }

    await api.storage.local.set({
      rpa4allUpdateRemoteVersion: remoteVersion,
      rpa4allUpdateCheckedAt: Date.now(),
      rpa4allUpdateUrl: data.url || '',
    });

    if (isNewerVersion(remoteVersion, CURRENT_VERSION)) {
      // Mostrar badge vermelho no ícone da extensão
      if (api.action && typeof api.action.setBadgeText === 'function') {
        api.action.setBadgeText({ text: 'NEW' });
        api.action.setBadgeBackgroundColor({ color: '#b42318' });
      }
      // Notificação do sistema (se suportada)
      if (api.notifications && typeof api.notifications.create === 'function') {
        api.notifications.create('rpa4all-update', {
          type: 'basic',
          iconUrl: api.runtime.getURL('icon128.png'),
          title: 'RPA4ALL Autofill — Atualização disponível',
          message: `Versão ${remoteVersion} disponível (instalada: ${CURRENT_VERSION}). Clique no ícone da extensão para atualizar.`,
        }).catch(() => {});
      }
    } else {
      // Remover badge se já está atualizado
      if (api.action && typeof api.action.setBadgeText === 'function') {
        api.action.setBadgeText({ text: '' });
      }
    }
  } catch (_) {
    // falha silenciosa — rede indisponível
  }
}

// ── Schedule update alarm ─────────────────────────────────────────────────
async function scheduleUpdateCheck() {
  await api.alarms.clear(UPDATE_CHECK_ALARM);
  api.alarms.create(UPDATE_CHECK_ALARM, {
    delayInMinutes: 1,
    periodInMinutes: UPDATE_CHECK_INTERVAL_MINUTES,
  });
}

function withSlash(base, path) {
  const safeBase = String(base || '').replace(/\/$/, '');
  const safePath = String(path || '').startsWith('/') ? String(path || '') : `/${String(path || '')}`;
  return `${safeBase}${safePath}`;
}

function normalizeRecord(raw, index) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const data = raw.data && typeof raw.data === 'object' ? raw.data : raw;
  const id = String(raw.id || raw.uuid || raw.key || index + 1);
  const label = String(raw.label || raw.name || raw.title || `Registro ${index + 1}`);
  return { id, label, data };
}

function extractRecords(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.records)
      ? payload.records
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.data)
          ? payload.data
          : payload?.data && typeof payload.data === 'object'
            ? [payload.data]
            : payload && typeof payload === 'object'
              ? [payload]
              : [];

  return list
    .map((item, index) => normalizeRecord(item, index))
    .filter(Boolean);
}

async function getSettings() {
  const stored = await api.storage.sync.get(Object.keys(DEFAULT_SETTINGS));
  return { ...DEFAULT_SETTINGS, ...stored };
}

function normalizeAutoRefreshMinutes(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return DEFAULT_SETTINGS.rpa4allAutoRefreshMinutes;
  }
  return Math.max(5, Math.min(24 * 60, Math.round(parsed)));
}

async function updateAutoRefreshAlarm() {
  const settings = await getSettings();
  await api.alarms.clear(AUTO_REFRESH_ALARM);
  if (!settings.rpa4allAutoRefreshEnabled) {
    return;
  }

  const periodInMinutes = normalizeAutoRefreshMinutes(settings.rpa4allAutoRefreshMinutes);
  api.alarms.create(AUTO_REFRESH_ALARM, { periodInMinutes });
}

async function fetchTestMasses(request) {
  const settings = await getSettings();
  const baseUrl = request.baseUrl || settings.rpa4allApiBaseUrl;
  const path = request.path || settings.rpa4allMassesPath;
  const query = (request.query || settings.rpa4allDefaultQuery || '').trim();
  const token = request.authToken != null ? request.authToken : settings.rpa4allAuthToken;
  const headers = { Accept: 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  async function fetchRecordsFrom(endpointPath) {
    const url = new URL(withSlash(baseUrl, endpointPath));
    if (query) {
      url.search = query.startsWith('?') ? query.slice(1) : query;
    }
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers,
      credentials: 'include'
    });

    if (!response.ok) {
      const body = await response.text().catch(() => '');
      const error = new Error(`Falha ${response.status}: ${body.slice(0, 180)}`);
      error.status = response.status;
      throw error;
    }

    const json = await response.json();
    return extractRecords(json);
  }

  let records = [];
  try {
    records = await fetchRecordsFrom(path);
  } catch (error) {
    if (error && error.status === 404 && path !== '/marketing/profile') {
      records = await fetchRecordsFrom('/marketing/profile');
    } else {
      throw error;
    }
  }

  if (!records.length) {
    throw new Error('Endpoint sem registros. Verifique o caminho em Opcoes.');
  }

  await api.storage.local.set({ rpa4allMassesCache: records, rpa4allMassesFetchedAt: Date.now() });
  return records;
}

async function getCachedMasses() {
  const result = await api.storage.local.get(['rpa4allMassesCache', 'rpa4allMassesFetchedAt']);
  return {
    records: Array.isArray(result.rpa4allMassesCache) ? result.rpa4allMassesCache : [],
    fetchedAt: Number(result.rpa4allMassesFetchedAt || 0)
  };
}

async function getMasses(request) {
  const settings = await getSettings();
  const cache = await getCachedMasses();
  const maxAgeMs = normalizeAutoRefreshMinutes(settings.rpa4allAutoRefreshMinutes) * 60 * 1000;
  const shouldRefresh = request.force === true
    || !cache.records.length
    || (settings.rpa4allAutoRefreshEnabled && (!cache.fetchedAt || (Date.now() - cache.fetchedAt) >= maxAgeMs));

  if (!shouldRefresh) {
    return { records: cache.records, fetchedAt: cache.fetchedAt, source: 'cache' };
  }

  const records = await fetchTestMasses(request);
  return { records, fetchedAt: Date.now(), source: 'api' };
}

api.runtime.onInstalled.addListener(() => {
  updateAutoRefreshAlarm().catch(() => {});
  scheduleUpdateCheck().catch(() => {});
  checkForUpdate().catch(() => {});
});

api.runtime.onStartup.addListener(() => {
  updateAutoRefreshAlarm().catch(() => {});
  scheduleUpdateCheck().catch(() => {});
  checkForUpdate().catch(() => {});
});

api.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== 'sync') {
    return;
  }
  if (changes.rpa4allAutoRefreshEnabled || changes.rpa4allAutoRefreshMinutes) {
    updateAutoRefreshAlarm().catch(() => {});
  }
});

api.alarms.onAlarm.addListener((alarm) => {
  if (!alarm) { return; }
  if (alarm.name === AUTO_REFRESH_ALARM) {
    getMasses({}).catch(() => {});
  }
  if (alarm.name === UPDATE_CHECK_ALARM) {
    checkForUpdate().catch(() => {});
  }
});

api.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (!request || typeof request !== 'object') {
    return false;
  }

  if (request.type === 'checkUpdate') {
    checkForUpdate()
      .then(() => api.storage.local.get(['rpa4allUpdateRemoteVersion', 'rpa4allUpdateCheckedAt', 'rpa4allUpdateUrl']))
      .then((data) => sendResponse({
        ok: true,
        remoteVersion: data.rpa4allUpdateRemoteVersion || null,
        currentVersion: CURRENT_VERSION,
        hasUpdate: isNewerVersion(data.rpa4allUpdateRemoteVersion || '', CURRENT_VERSION),
        url: data.rpa4allUpdateUrl || '',
        checkedAt: data.rpa4allUpdateCheckedAt || null,
      }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (request.type === 'getUpdateInfo') {
    api.storage.local.get(['rpa4allUpdateRemoteVersion', 'rpa4allUpdateCheckedAt', 'rpa4allUpdateUrl'])
      .then((data) => sendResponse({
        ok: true,
        remoteVersion: data.rpa4allUpdateRemoteVersion || null,
        currentVersion: CURRENT_VERSION,
        hasUpdate: isNewerVersion(data.rpa4allUpdateRemoteVersion || '', CURRENT_VERSION),
        url: data.rpa4allUpdateUrl || '',
        checkedAt: data.rpa4allUpdateCheckedAt || null,
      }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (request.type === 'fetchTestMasses') {
    fetchTestMasses(request)
      .then((records) => sendResponse({ ok: true, records }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (request.type === 'getMasses') {
    getMasses(request || {})
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (request.type === 'getSettings') {
    getSettings()
      .then((settings) => sendResponse({ ok: true, settings }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  return false;
});
