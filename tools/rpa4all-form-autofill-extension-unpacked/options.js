const api = typeof browser !== 'undefined' ? browser : chrome;

const DEFAULTS = {
  rpa4allApiBaseUrl: 'https://api.rpa4all.com/agents-api',
  rpa4allMassesPath: '/marketing/profile',
  rpa4allAuthToken: '',
  rpa4allDefaultQuery: '',
  rpa4allAutoRefreshEnabled: true,
  rpa4allAutoRefreshMinutes: 30
};

const fields = {
  apiBaseUrl: document.getElementById('apiBaseUrl'),
  massesPath: document.getElementById('massesPath'),
  authToken: document.getElementById('authToken'),
  defaultQuery: document.getElementById('defaultQuery'),
  autoRefreshEnabled: document.getElementById('autoRefreshEnabled'),
  autoRefreshMinutes: document.getElementById('autoRefreshMinutes')
};

const statusNode = document.getElementById('status');

function setStatus(message, isError) {
  statusNode.textContent = message;
  statusNode.style.color = isError ? '#b42318' : '#5f6b7a';
}

function storageGet(keys) {
  return new Promise((resolve, reject) => {
    api.storage.sync.get(keys, (result) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(result);
    });
  });
}

function storageSet(values) {
  return new Promise((resolve, reject) => {
    api.storage.sync.set(values, () => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve();
    });
  });
}

async function loadSettings() {
  const current = await storageGet(Object.keys(DEFAULTS));
  const data = { ...DEFAULTS, ...current };
  fields.apiBaseUrl.value = data.rpa4allApiBaseUrl;
  fields.massesPath.value = data.rpa4allMassesPath;
  fields.authToken.value = data.rpa4allAuthToken;
  fields.defaultQuery.value = data.rpa4allDefaultQuery;
  fields.autoRefreshEnabled.checked = Boolean(data.rpa4allAutoRefreshEnabled);
  fields.autoRefreshMinutes.value = String(data.rpa4allAutoRefreshMinutes);
}

async function saveSettings() {
  const autoRefreshMinutes = Math.max(5, Math.min(1440, Number(fields.autoRefreshMinutes.value || DEFAULTS.rpa4allAutoRefreshMinutes)));
  await storageSet({
    rpa4allApiBaseUrl: fields.apiBaseUrl.value.trim(),
    rpa4allMassesPath: fields.massesPath.value.trim(),
    rpa4allAuthToken: fields.authToken.value.trim(),
    rpa4allDefaultQuery: fields.defaultQuery.value.trim(),
    rpa4allAutoRefreshEnabled: fields.autoRefreshEnabled.checked,
    rpa4allAutoRefreshMinutes: autoRefreshMinutes
  });
  setStatus('Configuracao salva.');
}

async function resetDefaults() {
  await storageSet(DEFAULTS);
  await loadSettings();
  setStatus('Valores padrao restaurados.');
}

document.getElementById('save').addEventListener('click', () => {
  saveSettings().catch((error) => setStatus(error.message || String(error), true));
});

document.getElementById('reset').addEventListener('click', () => {
  resetDefaults().catch((error) => setStatus(error.message || String(error), true));
});

loadSettings().catch((error) => {
  setStatus(error.message || String(error), true);
});
