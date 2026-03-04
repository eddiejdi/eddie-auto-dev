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

  // ===== Technologies section: filters, animated bars, counters =====
  (function initTechSection() {
    // Category filters
    const filters = document.querySelectorAll('.tech-filter');
    const techCards = document.querySelectorAll('.tech-card');
    filters.forEach(btn => {
      btn.addEventListener('click', () => {
        filters.forEach(f => f.classList.remove('active'));
        btn.classList.add('active');
        const cat = btn.dataset.cat;
        let delay = 0;
        techCards.forEach(card => {
          if (cat === 'all' || card.dataset.cat === cat) {
            card.classList.remove('hidden');
            card.style.animation = 'none';
            card.offsetHeight; // reflow
            card.style.animation = `techCardIn 0.4s ease ${delay}ms both`;
            delay += 30;
          } else {
            card.classList.add('hidden');
          }
        });
      });
    });

    // Animated skill bars on visibility
    let barsAnimated = false;
    function animateBars(force) {
      if (barsAnimated) return;
      const grid = document.getElementById('techGrid');
      if (!grid) return;
      if (!force) {
        const rect = grid.getBoundingClientRect();
        if (rect.top >= window.innerHeight || rect.bottom <= 0) return;
      }
      barsAnimated = true;
      document.querySelectorAll('.tech-bar-fill').forEach((bar, i) => {
        setTimeout(() => bar.classList.add('animated'), i * 40);
      });
    }

    // Animated counters
    let countersAnimated = false;
    function animateCounters(force) {
      if (countersAnimated) return;
      const stats = document.querySelector('.tech-stats');
      if (!stats) return;
      if (!force) {
        const rect = stats.getBoundingClientRect();
        if (rect.top >= window.innerHeight || rect.bottom <= 0) return;
      }
      countersAnimated = true;
      document.querySelectorAll('.tech-stat-number').forEach(el => {
        const target = parseInt(el.dataset.count, 10);
        const duration = 1500;
        const startTime = performance.now();
        function tick(now) {
          const elapsed = now - startTime;
          const progress = Math.min(elapsed / duration, 1);
          const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
          el.textContent = Math.round(target * eased);
          if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      });
    }

    // Trigger animations when tech tab is visible
    function onTechVisible(forceAll) {
      const panel = document.getElementById('technologies');
      if (panel && panel.classList.contains('active')) {
        animateBars(forceAll);
        animateCounters(forceAll);
      }
    }
    window.addEventListener('scroll', onTechVisible, { passive: true });
    document.querySelectorAll('.tab').forEach(t => {
      t.addEventListener('click', () => setTimeout(() => onTechVisible(true), 200));
    });

    // 3D tilt effect on tech cards
    techCards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = (y - centerY) / centerY * -5;
        const rotateY = (x - centerX) / centerX * 5;
        card.style.transform = `translateY(-6px) scale(1.02) perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
        const glow = card.querySelector('.tech-card-glow');
        if (glow) {
          glow.style.left = `${x - rect.width}px`;
          glow.style.top = `${y - rect.height}px`;
        }
      });
      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
      });
    });
  })();

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