(function () {
  const api = typeof browser !== 'undefined' ? browser : chrome;

  api.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || message.type !== 'fillForm') {
      return false;
    }

    try {
      const core = globalThis.RPA4AllAutofillCore;
      if (!core || typeof core.fillForm !== 'function') {
        throw new Error('Autofill core indisponivel na pagina.');
      }
      const result = core.fillForm(message.payload || {});
      sendResponse({ ok: true, result });
    } catch (error) {
      sendResponse({ ok: false, error: error.message || String(error) });
    }

    return true;
  });
})();
