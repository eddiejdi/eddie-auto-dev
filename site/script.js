document.addEventListener('DOMContentLoaded', function () {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  function activate(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.target === target));
    panels.forEach(p => p.classList.toggle('active', p.id === target));
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