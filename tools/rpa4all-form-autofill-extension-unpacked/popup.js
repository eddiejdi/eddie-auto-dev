const api = typeof browser !== 'undefined' ? browser : chrome;

const statusNode = document.getElementById('status');
const recordSelect = document.getElementById('recordSelect');
const loadRemoteButton = document.getElementById('loadRemote');
const loadSampleButton = document.getElementById('loadSample');
const fillCurrentButton = document.getElementById('fillCurrent');
const openOptionsButton = document.getElementById('openOptions');

let records = [];

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

async function loadFromCache() {
  const result = await getStorageLocal(['rpa4allMassesCache']);
  records = Array.isArray(result.rpa4allMassesCache) ? result.rpa4allMassesCache : [];
  renderRecords();
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
  const selected = records[index];
  if (!selected || !selected.data) {
    throw new Error('Registro invalido.');
  }

  const tab = await queryActiveTab();
  if (!tab || !tab.id || !tab.url) {
    throw new Error('Nao foi possivel identificar a aba ativa.');
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
