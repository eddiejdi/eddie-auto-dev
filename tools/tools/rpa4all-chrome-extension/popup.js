const api = typeof browser !== 'undefined' ? browser : chrome;

const statusNode = document.getElementById('status');
const appVersionNode = document.getElementById('appVersion');
const recordSelect = document.getElementById('recordSelect');
const loadRemoteButton = document.getElementById('loadRemote');
const loadSampleButton = document.getElementById('loadSample');
const fillCurrentButton = document.getElementById('fillCurrent');
const openOptionsButton = document.getElementById('openOptions');

let records = [];
let activeTabSnapshot = null;

if (appVersionNode) {
  appVersionNode.textContent = `Versão ${api.runtime.getManifest().version}`;
}

function setStatus(message, isError) {
  statusNode.textContent = message;
  statusNode.style.color = isError ? '#b42318' : '#5f6b7a';
}

function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    api.runtime.sendMessage(message, (response) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(response);
    });
  });
}

function getStorageLocal(keys) {
  return new Promise((resolve, reject) => {
    api.storage.local.get(keys, (result) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(result);
    });
  });
}

function setStorageLocal(data) {
  return new Promise((resolve, reject) => {
    api.storage.local.set(data, () => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve();
    });
  });
}

function queryActiveTab() {
  return new Promise((resolve, reject) => {
    api.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve((tabs || [])[0]);
    });
  });
}

function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    api.tabs.sendMessage(tabId, message, (response) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(response);
    });
  });
}

function injectAutofillCore(tabId) {
  return new Promise((resolve, reject) => {
    api.scripting.executeScript(
      {
        target: { tabId },
        files: ['autofill-core.js']
      },
      () => {
        const err = api.runtime.lastError;
        if (err) {
          reject(new Error(err.message));
          return;
        }
        resolve();
      }
    );
  });
}

function executeScriptFill(tabId, payload) {
  return injectAutofillCore(tabId).then(() => new Promise((resolve, reject) => {
    api.scripting.executeScript(
      {
        target: { tabId },
        func: (data) => {
          const core = globalThis.RPA4AllAutofillCore;
          if (!core || typeof core.fillForm !== 'function') {
            throw new Error('Autofill core indisponivel no fallback.');
          }
          const result = core.fillForm(data || {});
          return { ...result, mode: 'script-fallback' };
        },
        args: [payload]
      },
      (results) => {
        const err = api.runtime.lastError;
        if (err) {
          reject(new Error(err.message));
          return;
        }
        resolve(results && results[0] ? results[0].result : { filled: 0, totalKeys: 0, mode: 'script-fallback' });
      }
    );
  }));
}

function renderRecords() {
  recordSelect.innerHTML = '';
  if (!records.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Sem registros';
    recordSelect.appendChild(option);
    recordSelect.disabled = true;
    return;
  }

  recordSelect.disabled = false;
  records.forEach((record, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `${record.label} (#${record.id})`;
    recordSelect.appendChild(option);
  });
}

function scoreRecordForPage(record, pageInfo) {
  const data = record && record.data && typeof record.data === 'object' ? record.data : {};
  const keys = Object.keys(data);
  const normalizedUrl = String((pageInfo && pageInfo.url) || '').toLowerCase();
  const markers = Array.isArray(pageInfo && pageInfo.markers) ? pageInfo.markers : [];
  let score = 0;

  if (normalizedUrl.includes('storage-request')) {
    if (keys.includes('company')) score += 50;
    if (keys.includes('legal_name')) score += 50;
    if (keys.includes('project')) score += 40;
    if (keys.includes('company_document')) score += 40;
  }

  if (normalizedUrl.includes('marketing-studio')) {
    if (keys.includes('theme')) score += 40;
    if (keys.includes('audience')) score += 40;
    if (keys.includes('tagline')) score += 30;
  }

  if (markers.includes('storage-request-form')) {
    if (keys.includes('company')) score += 80;
    if (keys.includes('legal_name')) score += 70;
    if (keys.includes('project')) score += 60;
    if (keys.includes('company_document')) score += 60;
  }

  if (markers.includes('marketing-studio-form')) {
    if (keys.includes('theme')) score += 80;
    if (keys.includes('audience')) score += 70;
    if (keys.includes('tagline')) score += 50;
  }

  return score;
}

async function inspectActiveTab(tabId) {
  return new Promise((resolve) => {
    api.scripting.executeScript(
      {
        target: { tabId },
        func: () => {
          const markers = [];
          if (document.getElementById('storageRequestForm') || document.getElementById('requestCompany')) {
            markers.push('storage-request-form');
          }
          if (document.getElementById('marketingTheme') || document.getElementById('businessCardName')) {
            markers.push('marketing-studio-form');
          }
          return { url: window.location.href, markers };
        }
      },
      (results) => {
        const err = api.runtime.lastError;
        if (err) {
          resolve(null);
          return;
        }
        resolve(results && results[0] ? results[0].result : null);
      }
    );
  });
}

async function autoSelectBestRecord() {
  if (!records.length) {
    return;
  }

  const tab = await queryActiveTab().catch(() => null);
  if (!tab || !tab.id) {
    return;
  }

  activeTabSnapshot = await inspectActiveTab(tab.id);
  if (!activeTabSnapshot) {
    activeTabSnapshot = { url: tab.url || '', markers: [] };
  }

  let bestIndex = 0;
  let bestScore = -1;
  records.forEach((record, index) => {
    const score = scoreRecordForPage(record, activeTabSnapshot);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });

  recordSelect.value = String(bestIndex);
}

function pickRecordForActivePage() {
  if (!records.length) {
    return null;
  }

  const selectedIndex = Number(recordSelect.value || 0);
  const selected = records[selectedIndex];
  const selectedScore = selected ? scoreRecordForPage(selected, activeTabSnapshot) : -1;

  let bestIndex = selectedIndex >= 0 ? selectedIndex : 0;
  let bestScore = selectedScore;
  records.forEach((record, index) => {
    const score = scoreRecordForPage(record, activeTabSnapshot);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });

  recordSelect.value = String(bestIndex);
  return records[bestIndex] || null;
}

async function loadFromCache() {
  const result = await getStorageLocal(['rpa4allMassesCache']);
  records = Array.isArray(result.rpa4allMassesCache) ? result.rpa4allMassesCache : [];
  renderRecords();
  await autoSelectBestRecord();
  if (records.length) {
    setStatus(`Cache carregado com ${records.length} registro(s).`);
  }
}

async function loadAutoUpdated() {
  const response = await sendRuntimeMessage({ type: 'getMasses' });
  if (!response || !response.ok) {
    throw new Error(response && response.error ? response.error : 'Falha ao obter massa atualizada.');
  }

  records = Array.isArray(response.records) ? response.records : [];
  renderRecords();
  await autoSelectBestRecord();
  if (records.length) {
    const sourceLabel = response.source === 'api' ? 'API' : 'cache';
    setStatus(`Massa carregada via ${sourceLabel} (${records.length} registro(s)).`);
  }
}

async function loadFromSample() {
  const response = await fetch(api.runtime.getURL('sample-masses.json'));
  const json = await response.json();
  records = Array.isArray(json.records) ? json.records : [];
  await setStorageLocal({ rpa4allMassesCache: records, rpa4allMassesFetchedAt: Date.now() });
  renderRecords();
  await autoSelectBestRecord();
  setStatus(`Massa local carregada (${records.length} registro(s)).`);
}

async function loadFromApi() {
  setStatus('Carregando massa de testes da API...');
  const response = await sendRuntimeMessage({ type: 'fetchTestMasses' });
  if (!response || !response.ok) {
    throw new Error(response && response.error ? response.error : 'Falha ao consultar API.');
  }
  records = response.records || [];
  renderRecords();
  await autoSelectBestRecord();
  setStatus(`API retornou ${records.length} registro(s).`);
}

async function fillCurrentTab() {
  if (!records.length) {
    await loadAutoUpdated();
  }

  if (!records.length) {
    await loadFromSample();
  }

  if (!records.length) {
    throw new Error('Nenhum registro carregado. Use "Carregar massa (API)" ou "Usar massa local".');
  }

  const index = Number(recordSelect.value || 0);
  const tab = await queryActiveTab();
  if (!tab || !tab.id || !tab.url) {
    throw new Error('Nao foi possivel identificar a aba ativa.');
  }

  activeTabSnapshot = await inspectActiveTab(tab.id);
  if (!activeTabSnapshot) {
    activeTabSnapshot = { url: tab.url || '', markers: [] };
  }

  const selected = pickRecordForActivePage() || records[index];
  if (!selected || !selected.data) {
    throw new Error('Registro invalido.');
  }

  let result = null;
  try {
    const response = await sendMessageToTab(tab.id, { type: 'fillForm', payload: selected.data });
    if (!response || !response.ok) {
      throw new Error(response && response.error ? response.error : 'Falha ao preencher formulario.');
    }
    result = response.result || {};
  } catch (error) {
    result = await executeScriptFill(tab.id, selected.data);
  }

  if (!result || Number(result.filled || 0) === 0) {
    result = await executeScriptFill(tab.id, selected.data);
  } else if (Number(result.filled || 0) < Number(result.totalKeys || 0)) {
    const fallback = await executeScriptFill(tab.id, selected.data);
    if (fallback && Number(fallback.filled || 0) >= Number(result.filled || 0)) {
      result = fallback;
    }
  }

  setStatus(`Preenchido: ${result.filled}/${result.totalKeys} campos.`);
}

loadRemoteButton.addEventListener('click', async () => {
  try {
    await loadFromApi();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

loadSampleButton.addEventListener('click', async () => {
  try {
    await loadFromSample();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

fillCurrentButton.addEventListener('click', async () => {
  try {
    await fillCurrentTab();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

openOptionsButton.addEventListener('click', () => {
  api.runtime.openOptionsPage();
});

// ── Banner de atualização ────────────────────────────────────────────────
const updateBanner = document.getElementById('updateBanner');
const updateBannerVersion = document.getElementById('updateBannerVersion');
const updateBannerLink = document.getElementById('updateBannerLink');

function showUpdateBanner(remoteVersion, url) {
  if (!updateBanner) { return; }
  if (updateBannerVersion) {
    updateBannerVersion.textContent = `v${remoteVersion}`;
  }
  if (updateBannerLink && url) {
    updateBannerLink.href = url;
  }
  updateBanner.style.display = 'block';
}

async function checkAndShowUpdate() {
  try {
    const response = await sendRuntimeMessage({ type: 'getUpdateInfo' });
    if (response && response.ok && response.hasUpdate && response.remoteVersion) {
      showUpdateBanner(response.remoteVersion, response.url);
    }
  } catch (_) {
    // silencioso
  }
}

checkAndShowUpdate();

loadFromCache().catch(() => {
  renderRecords();
});

setTimeout(() => {
  loadAutoUpdated().catch(() => {
    if (!records.length) {
      loadFromSample().catch(() => {
        setStatus('Nenhum registro em cache. Clique em "Usar massa local" ou "Carregar massa (API)".', true);
      });
    }
  });
}, 0);
