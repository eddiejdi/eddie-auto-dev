const api = typeof browser !== 'undefined' ? browser : chrome;

const DEFAULT_SETTINGS = {
  rpa4allApiBaseUrl: 'https://api.rpa4all.com/agents-api',
  rpa4allMassesPath: '/marketing/profile',
  rpa4allAuthToken: '',
  rpa4allDefaultQuery: ''
};

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

api.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (!request || typeof request !== 'object') {
    return false;
  }

  if (request.type === 'fetchTestMasses') {
    fetchTestMasses(request)
      .then((records) => sendResponse({ ok: true, records }))
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
