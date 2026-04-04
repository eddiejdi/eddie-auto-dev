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
const IS_TEST_ENV = Boolean(globalThis.__RPA4ALL_POPUP_TEST__);

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

function getPopupTargeting() {
  try {
    const search = globalThis.location && typeof globalThis.location.search === 'string'
      ? globalThis.location.search
      : '';
    const params = new URLSearchParams(search);
    const targetTabId = Number(params.get('targetTabId') || '');
    const targetUrl = (params.get('targetUrl') || '').trim();
    return {
      targetTabId: Number.isFinite(targetTabId) && targetTabId > 0 ? targetTabId : null,
      targetUrl
    };
  } catch (_) {
    return { targetTabId: null, targetUrl: '' };
  }
}

function queryTargetTabByUrl(targetUrl) {
  return new Promise((resolve, reject) => {
    api.tabs.query({}, (tabs) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      const normalizedTarget = String(targetUrl || '').trim();
      const matched = (tabs || []).find((tab) => String(tab.url || '').includes(normalizedTarget));
      resolve(matched || null);
    });
  });
}

async function resolveTargetTab() {
  const targeting = getPopupTargeting();
  if (targeting.targetTabId) {
    return { id: targeting.targetTabId };
  }
  if (targeting.targetUrl) {
    const matched = await queryTargetTabByUrl(targeting.targetUrl).catch(() => null);
    if (matched) {
      return matched;
    }
  }
  return queryActiveTab();
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
      // Try to ping content script first; if not present, inject autofill-core.js
      api.tabs.sendMessage(tabId, { type: '__rpa4all_ping' }, (resp) => {
        const err = api.runtime.lastError;
        if (!err) {
          resolve();
          return;
        }
        try {
          api.tabs.executeScript(tabId, { file: 'autofill-core.js' }, () => {
            const err2 = api.runtime.lastError;
            if (err2) {
              reject(new Error(err2.message));
              return;
            }
            resolve();
          });
        } catch (e) {
          reject(e);
        }
      });
    });
}

function executeScriptFill(tabId, payload) {
    return injectAutofillCore(tabId).then(() => new Promise((resolve, reject) => {
    api.tabs.sendMessage(tabId, { type: 'fillForm', payload }, (response) => {
      const err = api.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      if (!response) {
        // no response from content script
        resolve({ filled: 0, totalKeys: 0, mode: 'script-fallback' });
        return;
      }
      if (!response.ok) {
        resolve({ filled: 0, totalKeys: 0, mode: 'script-fallback', error: response.error });
        return;
      }
      resolve(response.result);
    });
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

function getPageProfile(pageInfo) {
  const normalizedUrl = String((pageInfo && pageInfo.url) || '').toLowerCase();
  const markers = Array.isArray(pageInfo && pageInfo.markers) ? pageInfo.markers : [];

  if (markers.includes('storage-request-form') || normalizedUrl.includes('storage-request')) {
    return 'storage';
  }

  if (markers.includes('marketing-studio-form') || normalizedUrl.includes('marketing-studio')) {
    return 'marketing';
  }

  return 'generic';
}

function isRecordCompatibleForPage(record, pageInfo) {
  const data = record && record.data && typeof record.data === 'object' ? record.data : {};
  const keys = Object.keys(data);
  const profile = getPageProfile(pageInfo);

  if (profile === 'storage') {
    return keys.includes('company') && keys.includes('legal_name') && keys.includes('project');
  }

  if (profile === 'marketing') {
    return keys.includes('theme') && keys.includes('audience') && keys.includes('name');
  }

  return keys.length > 0;
}

function findBestRecordForPage(sourceRecords, pageInfo) {
  let bestIndex = 0;
  let bestScore = -1;

  sourceRecords.forEach((record, index) => {
    const score = scoreRecordForPage(record, pageInfo);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });

  const bestRecord = sourceRecords[bestIndex] || null;
  return {
    index: bestIndex,
    score: bestScore,
    record: bestRecord,
    compatible: isRecordCompatibleForPage(bestRecord, pageInfo)
  };
}

  async function inspectActiveTab(tabId) {
    return new Promise((resolve) => {
      try {
        api.tabs.executeScript(tabId, {
          code: `(function(){
            const markers = [];
            if (document.getElementById('storageRequestForm') || document.getElementById('requestCompany')) markers.push('storage-request-form');
            if (document.getElementById('marketingTheme') || document.getElementById('businessCardName')) markers.push('marketing-studio-form');
            return { url: window.location.href, markers };
          })();`
        }, (results) => {
          const err = api.runtime.lastError;
          if (err) {
            resolve(null);
            return;
          }
          resolve(results && results[0] ? results[0] : null);
        });
      } catch (e) {
        resolve(null);
      }
    });
  }

async function autoSelectBestRecord() {
  if (!records.length) {
    return;
  }

  const tab = await resolveTargetTab().catch(() => null);
  if (!tab || !tab.id) {
    return;
  }

  activeTabSnapshot = await inspectActiveTab(tab.id);
  if (!activeTabSnapshot) {
    activeTabSnapshot = { url: tab.url || '', markers: [] };
  }

  const bestMatch = findBestRecordForPage(records, activeTabSnapshot);
  recordSelect.value = String(bestMatch.index);
}

function pickRecordForActivePage() {
  if (!records.length) {
    return { record: null, index: -1, score: -1, compatible: false };
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
  const bestRecord = records[bestIndex] || null;
  return {
    record: bestRecord,
    index: bestIndex,
    score: bestScore,
    compatible: isRecordCompatibleForPage(bestRecord, activeTabSnapshot)
  };
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
    if (response.apiError) {
      setStatus(`API indisponível — usando cache (${records.length} registro(s)).`);
    } else {
      const sourceLabel = response.source === 'api' ? 'API' : 'cache';
      setStatus(`Massa carregada via ${sourceLabel} (${records.length} registro(s)).`);
    }
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
  let usedLocalCompatibilityFallback = false;

  if (!records.length) {
    await loadAutoUpdated().catch(() => {});
  }

  if (!records.length) {
    await loadFromSample();
  }

  if (!records.length) {
    throw new Error('Nenhum registro carregado. Use "Carregar massa (API)" ou "Usar massa local".');
  }

  const index = Number(recordSelect.value || 0);
  const tab = await resolveTargetTab();
  if (!tab || !tab.id || !tab.url) {
    throw new Error('Nao foi possivel identificar a aba ativa.');
  }

  activeTabSnapshot = await inspectActiveTab(tab.id);
  if (!activeTabSnapshot) {
    activeTabSnapshot = { url: tab.url || '', markers: [] };
  }

  let selectedMatch = pickRecordForActivePage();

  if ((!selectedMatch || !selectedMatch.compatible) && getPageProfile(activeTabSnapshot) !== 'generic') {
    await loadFromSample();
    usedLocalCompatibilityFallback = true;
    selectedMatch = pickRecordForActivePage();
  }

  const selected = (selectedMatch && selectedMatch.record) || records[index];
  if (!selected || !selected.data) {
    throw new Error('Registro invalido.');
  }

  if (!isRecordCompatibleForPage(selected, activeTabSnapshot) && getPageProfile(activeTabSnapshot) !== 'generic') {
    throw new Error('Nenhuma massa compativel com a pagina ativa foi encontrada.');
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

  setStatus(`Preenchido: ${result.filled}/${result.totalKeys} campos.${usedLocalCompatibilityFallback ? ' Usando massa local compativel.' : ''}`);
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

if (IS_TEST_ENV) {
  globalThis.__RPA4ALL_POPUP_EXPORTS = {
    scoreRecordForPage,
    getPageProfile,
    isRecordCompatibleForPage,
    findBestRecordForPage
  };
} else {
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
}
