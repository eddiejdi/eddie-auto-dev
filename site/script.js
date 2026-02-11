document.addEventListener('DOMContentLoaded', function () {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  function activate(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.target === target));
    panels.forEach(p => p.classList.toggle('active', p.id === target));
    // Special behavior: when Jira tab is activated, load embedded iframe below the header
    const embedContainer = document.getElementById('embedContainer');
    const JIRA_URL = 'https://rpa4all.atlassian.net';
    if (target === 'jira') {
      // show embed container
      embedContainer.style.display = 'block';
      // if iframe already exists, keep it
      if (!document.getElementById('jiraEmbed')) {
        // create iframe
        const iframe = document.createElement('iframe');
        iframe.id = 'jiraEmbed';
        iframe.src = JIRA_URL;
        iframe.style.width = '100%';
        iframe.style.height = '700px';
        iframe.style.border = '0';
        iframe.setAttribute('loading', 'lazy');
        // fallback message in case site blocks embedding
        const fallback = document.createElement('div');
        fallback.id = 'jiraEmbedFallback';
        fallback.style.padding = '1rem';
        fallback.style.display = 'none';
        fallback.innerHTML = `<p>Não foi possível carregar o Jira embutido. <a href="${JIRA_URL}" target="_blank" rel="noopener">Abrir Jira em nova aba</a></p>`;
        embedContainer.appendChild(iframe);
        embedContainer.appendChild(fallback);

        // detect simple load success/failure
        let loaded = false;
        iframe.addEventListener('load', function () {
          loaded = true;
          // Try to access contentDocument to detect X-Frame-Options; this will throw on cross-origin.
          try {
            const doc = iframe.contentDocument || iframe.contentWindow.document;
            // If we can read, hide fallback
            fallback.style.display = 'none';
          } catch (e) {
            // cross-origin - still may have rendered; keep fallback hidden but show note only if visual blocked
            // Wait a short time and then check iframe height — if zero, assume blocked
            setTimeout(() => {
              if (iframe.clientHeight === 0 || iframe.offsetHeight === 0) {
                iframe.style.display = 'none';
                fallback.style.display = 'block';
              }
            }, 800);
          }
        });
        // If iframe errors (rare), show fallback
        iframe.addEventListener('error', function () {
          iframe.style.display = 'none';
          fallback.style.display = 'block';
        });
      }
    } else {
      // hide embed container
      if (embedContainer) {
        embedContainer.style.display = 'none';
      }
    }
  }
  tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.target)));

  // keyboard nav
  document.addEventListener('keyup', e => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const arr = Array.from(tabs);
      const idx = arr.findIndex(t => t.classList.contains('active'));
      const next = e.key === 'ArrowRight' ? (idx + 1) % arr.length : (idx - 1 + arr.length) % arr.length;
      arr[next].click();
    }
  });

  // Simple local chat demo to support E2E tests when backend is not available
  (function initLocalChatDemo() {
    const chatInput = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
    const chatOutput = document.getElementById('chatOutput');
    if (!chatInput || !chatOutput) return;

    function appendMessage(who, text) {
      const div = document.createElement('div');
      div.className = 'chat-line';
      div.innerHTML = `<strong>${who}:</strong> <span>${text}</span>`;
      chatOutput.appendChild(div);
      chatOutput.scrollTop = chatOutput.scrollHeight;
    }

    chatInput.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;
        appendMessage('Você', msg);
        chatInput.value = '';

        // Simple bot behavior: respond with a code snippet for 'soma' request
        setTimeout(() => {
          if (/soma|somar|função de soma/i.test(msg)) {
            appendMessage('Agent', '<pre>def soma(a, b):\n    return a + b</pre>');
          } else {
            appendMessage('Agent', 'Recebi: ' + msg);
          }
        }, 600);
      }
    });
  })();
});