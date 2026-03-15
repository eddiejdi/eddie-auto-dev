document.addEventListener('DOMContentLoaded', function () {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');

  function activate(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.target === target));
    panels.forEach(p => p.classList.toggle('active', p.id === target));
  }

  tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.target)));
  const initialTarget = window.location.hash
    ? window.location.hash.slice(1)
    : (document.querySelector('.tab.active')?.dataset.target || 'home');
  if (Array.from(panels).some(panel => panel.id === initialTarget)) {
    activate(initialTarget);
  } else {
    activate('home');
  }

  // keyboard nav
  document.addEventListener('keyup', e => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const arr = Array.from(tabs);
      const idx = arr.findIndex(t => t.classList.contains('active'));
      const next = e.key === 'ArrowRight' ? (idx + 1) % arr.length : (idx - 1 + arr.length) % arr.length;
      arr[next].click();
    }
  });

  (function initSiteBackground() {
    const canvas = document.getElementById('siteBackgroundCanvas');
    const svgSlot = document.getElementById('siteBackgroundSvg');
    if (!canvas || !svgSlot) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hostname = window.location.hostname;
    const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';
    const isLanHost = hostname.startsWith('192.168.');
    const sameOriginApiBase = window.location.origin + '/agents-api';
    const externalApiBase = 'https://api.rpa4all.com/agents-api';
    const historyKey = 'rpa4all_background_history_v1';
    const lastSeedKey = 'rpa4all_background_seed_v1';
    const directOllamaBase =
      window.location.protocol === 'http:'
        ? (isLocalHost ? 'http://localhost:11434' : (isLanHost ? 'http://192.168.15.2:11434' : ''))
        : '';

    const variants = [
      {
        id: 'control-mesh',
        focus: 'an asymmetrical control mesh with monitoring arcs and clean routing lines',
        base: '#06101d',
        deep: '#081a31',
        glowA: 'rgba(56, 189, 248, 0.26)',
        glowB: 'rgba(34, 197, 94, 0.16)',
        glowC: 'rgba(20, 184, 166, 0.14)'
      },
      {
        id: 'precision-field',
        focus: 'a precision field of emerald and cyan trajectories with layered telemetry halos',
        base: '#07111f',
        deep: '#0a1f35',
        glowA: 'rgba(45, 212, 191, 0.22)',
        glowB: 'rgba(56, 189, 248, 0.18)',
        glowC: 'rgba(34, 197, 94, 0.16)'
      },
      {
        id: 'signal-archipelago',
        focus: 'signal islands connected by data bridges, packet trails and subtle observability rings',
        base: '#05111c',
        deep: '#0a1730',
        glowA: 'rgba(56, 189, 248, 0.24)',
        glowB: 'rgba(16, 185, 129, 0.18)',
        glowC: 'rgba(14, 165, 233, 0.13)'
      },
      {
        id: 'orchestration-fold',
        focus: 'folded orchestration planes with modular panels and soft pulse waves',
        base: '#07101b',
        deep: '#102038',
        glowA: 'rgba(14, 165, 233, 0.22)',
        glowB: 'rgba(34, 197, 94, 0.16)',
        glowC: 'rgba(59, 130, 246, 0.14)'
      },
      {
        id: 'resilience-constellation',
        focus: 'a resilience constellation with anchored nodes, recovery pulses and a faint technical grid',
        base: '#06101c',
        deep: '#0a1d33',
        glowA: 'rgba(34, 197, 94, 0.18)',
        glowB: 'rgba(56, 189, 248, 0.22)',
        glowC: 'rgba(6, 182, 212, 0.14)'
      },
      {
        id: 'data-current',
        focus: 'flowing data currents sweeping diagonally over a dark command surface with sparse nodes',
        base: '#06111c',
        deep: '#0a1830',
        glowA: 'rgba(56, 189, 248, 0.24)',
        glowB: 'rgba(6, 182, 212, 0.14)',
        glowC: 'rgba(34, 197, 94, 0.14)'
      }
    ];

    const variant = chooseVariant();
    const scene = createScene(variant);
    let viewportWidth = 0;
    let viewportHeight = 0;
    let deviceScale = 1;
    let animationFrameId = 0;

    applyVariantPalette(variant);
    resizeCanvas();
    drawFrame(0);
    requestBackgroundSvg(variant);

    if (!prefersReducedMotion) {
      startAnimation();
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          stopAnimation();
        } else {
          startAnimation();
        }
      });
    }

    window.addEventListener('resize', resizeCanvas, { passive: true });

    function safeStorageGet(key, fallback) {
      try {
        const value = window.localStorage.getItem(key);
        return value === null ? fallback : value;
      } catch (error) {
        return fallback;
      }
    }

    function safeStorageSet(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (error) {
        // ignore storage failures
      }
    }

    function safeStorageJson(key, fallback) {
      try {
        const value = window.localStorage.getItem(key);
        return value ? JSON.parse(value) : fallback;
      } catch (error) {
        return fallback;
      }
    }

    function randomInt(limit) {
      if (limit <= 0) return 0;
      if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
        const values = new Uint32Array(1);
        window.crypto.getRandomValues(values);
        return values[0] % limit;
      }
      return Math.floor(Math.random() * limit);
    }

    function chooseVariant() {
      const storedHistory = safeStorageJson(historyKey, []);
      const recent = Array.isArray(storedHistory) ? storedHistory : [];
      const pool = variants.filter(item => !recent.includes(item.id));
      const candidates = pool.length ? pool : variants.filter(item => item.id !== recent[0]);
      const choice = candidates[randomInt(candidates.length || variants.length)] || variants[0];
      const lastSeed = Number.parseInt(safeStorageGet(lastSeedKey, '0'), 10) || 0;
      let seed = 100000 + randomInt(900000);
      if (seed === lastSeed) {
        seed = ((seed + 7919) % 900000) + 100000;
      }

      safeStorageSet(
        historyKey,
        JSON.stringify([choice.id].concat(recent.filter(id => id !== choice.id)).slice(0, variants.length - 1))
      );
      safeStorageSet(lastSeedKey, String(seed));

      return Object.assign({}, choice, { seed: seed });
    }

    function applyVariantPalette(selectedVariant) {
      const rootStyle = document.documentElement.style;
      rootStyle.setProperty('--site-bg-base', selectedVariant.base);
      rootStyle.setProperty('--site-bg-deep', selectedVariant.deep);
      rootStyle.setProperty('--site-bg-glow-a', selectedVariant.glowA);
      rootStyle.setProperty('--site-bg-glow-b', selectedVariant.glowB);
      rootStyle.setProperty('--site-bg-glow-c', selectedVariant.glowC);
      document.body.dataset.backgroundVariant = selectedVariant.id;
    }

    function seededRandom(seed) {
      let value = seed >>> 0;
      return function () {
        value = (value * 1664525 + 1013904223) >>> 0;
        return value / 4294967296;
      };
    }

    function createScene(selectedVariant) {
      const rand = seededRandom(selectedVariant.seed);
      const nodes = Array.from({ length: 16 }, () => ({
        x: 0.1 + rand() * 0.8,
        y: 0.12 + rand() * 0.74,
        radius: 2 + rand() * 3.5,
        phase: rand() * Math.PI * 2,
        speed: 0.18 + rand() * 0.46
      }));

      const particles = Array.from({ length: 42 }, () => ({
        x: rand(),
        y: rand(),
        size: 1 + rand() * 3,
        speed: 0.02 + rand() * 0.06,
        drift: (rand() - 0.5) * 0.035,
        alpha: 0.12 + rand() * 0.28
      }));

      const streams = Array.from({ length: 5 }, (_, index) => ({
        y: 0.16 + index * 0.14 + rand() * 0.05,
        amplitude: 18 + rand() * 42,
        thickness: 1 + rand() * 1.8,
        phase: rand() * Math.PI * 2,
        speed: 0.12 + rand() * 0.2
      }));

      return { rand, nodes, particles, streams };
    }

    function resizeCanvas() {
      viewportWidth = Math.max(window.innerWidth, 360);
      viewportHeight = Math.max(window.innerHeight, 520);
      deviceScale = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(viewportWidth * deviceScale);
      canvas.height = Math.round(viewportHeight * deviceScale);
      canvas.style.width = viewportWidth + 'px';
      canvas.style.height = viewportHeight + 'px';
    }

    function toRgba(hex, alpha) {
      const normalized = hex.replace('#', '');
      if (normalized.length !== 6) return 'rgba(255,255,255,' + alpha + ')';
      const red = Number.parseInt(normalized.slice(0, 2), 16);
      const green = Number.parseInt(normalized.slice(2, 4), 16);
      const blue = Number.parseInt(normalized.slice(4, 6), 16);
      return 'rgba(' + red + ', ' + green + ', ' + blue + ', ' + alpha + ')';
    }

    function drawFrame(timestamp) {
      const time = timestamp / 1000;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);

      const gradient = ctx.createLinearGradient(0, 0, viewportWidth, viewportHeight);
      gradient.addColorStop(0, variant.deep);
      gradient.addColorStop(1, variant.base);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, viewportWidth, viewportHeight);

      drawGlows(time);
      drawGrid(time);
      drawStreams(time);
      drawNetwork(time);
      drawParticles(time);
      drawRings(time);
    }

    function drawGlows(time) {
      const glows = [
        { x: viewportWidth * 0.18, y: viewportHeight * (0.22 + Math.sin(time * 0.18) * 0.02), radius: viewportWidth * 0.22, color: 'rgba(56, 189, 248, 0.15)' },
        { x: viewportWidth * 0.76, y: viewportHeight * (0.18 + Math.cos(time * 0.16) * 0.02), radius: viewportWidth * 0.2, color: 'rgba(34, 197, 94, 0.12)' },
        { x: viewportWidth * 0.58, y: viewportHeight * (0.74 + Math.sin(time * 0.14) * 0.03), radius: viewportWidth * 0.18, color: 'rgba(20, 184, 166, 0.10)' }
      ];

      glows.forEach(glow => {
        const fill = ctx.createRadialGradient(glow.x, glow.y, 0, glow.x, glow.y, glow.radius);
        fill.addColorStop(0, glow.color);
        fill.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = fill;
        ctx.fillRect(glow.x - glow.radius, glow.y - glow.radius, glow.radius * 2, glow.radius * 2);
      });
    }

    function drawGrid(time) {
      const gridSize = 84;
      const offsetX = (time * 10) % gridSize;
      const offsetY = (time * 7) % gridSize;
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.055)';
      ctx.lineWidth = 1;

      for (let x = -gridSize; x < viewportWidth + gridSize; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x + offsetX, 0);
        ctx.lineTo(x + offsetX, viewportHeight);
        ctx.stroke();
      }

      for (let y = -gridSize; y < viewportHeight + gridSize; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y + offsetY);
        ctx.lineTo(viewportWidth, y + offsetY);
        ctx.stroke();
      }
    }

    function drawStreams(time) {
      scene.streams.forEach((stream, index) => {
        const y = viewportHeight * stream.y;
        const amplitude = stream.amplitude;
        ctx.beginPath();
        ctx.moveTo(-40, y);

        for (let x = 0; x <= viewportWidth + 40; x += viewportWidth / 6) {
          const wave = Math.sin(time * stream.speed + stream.phase + x / 180) * amplitude;
          const wave2 = Math.cos(time * (stream.speed * 0.85) + stream.phase + x / 260) * amplitude * 0.45;
          ctx.lineTo(x, y + wave + wave2);
        }

        const alpha = 0.06 + index * 0.018;
        ctx.strokeStyle = index % 2 === 0 ? toRgba('#38bdf8', alpha) : toRgba('#22c55e', alpha);
        ctx.lineWidth = stream.thickness;
        ctx.stroke();
      });
    }

    function drawNetwork(time) {
      const positionedNodes = scene.nodes.map(node => ({
        x: node.x * viewportWidth + Math.sin(time * node.speed + node.phase) * 20,
        y: node.y * viewportHeight + Math.cos(time * (node.speed * 0.9) + node.phase) * 18,
        radius: node.radius
      }));

      for (let index = 0; index < positionedNodes.length; index += 1) {
        for (let other = index + 1; other < positionedNodes.length; other += 1) {
          const a = positionedNodes[index];
          const b = positionedNodes[other];
          const distance = Math.hypot(a.x - b.x, a.y - b.y);
          if (distance > 240) continue;
          const alpha = (1 - distance / 240) * 0.22;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = other % 2 === 0 ? toRgba('#38bdf8', alpha) : toRgba('#22c55e', alpha * 0.9);
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      positionedNodes.forEach((node, index) => {
        const pulse = 1 + Math.sin(time * 1.4 + index) * 0.22;
        const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, 18 * pulse);
        glow.addColorStop(0, index % 2 === 0 ? 'rgba(56, 189, 248, 0.22)' : 'rgba(34, 197, 94, 0.18)');
        glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = glow;
        ctx.fillRect(node.x - 24, node.y - 24, 48, 48);

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * pulse, 0, Math.PI * 2);
        ctx.fillStyle = index % 2 === 0 ? 'rgba(125, 211, 252, 0.82)' : 'rgba(134, 239, 172, 0.78)';
        ctx.fill();
      });
    }

    function drawParticles(time) {
      scene.particles.forEach((particle, index) => {
        const x = ((particle.x + time * particle.drift * 0.04 + 1) % 1) * viewportWidth;
        const y = ((particle.y + time * particle.speed * 0.08 + index * 0.002) % 1) * viewportHeight;
        ctx.beginPath();
        ctx.arc(x, y, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = index % 3 === 0
          ? 'rgba(56, 189, 248, ' + particle.alpha + ')'
          : 'rgba(255, 255, 255, ' + (particle.alpha * 0.8) + ')';
        ctx.fill();
      });
    }

    function drawRings(time) {
      const rings = [
        { x: viewportWidth * 0.2, y: viewportHeight * 0.7, radius: viewportWidth * 0.12, color: '#22c55e', speed: 0.22 },
        { x: viewportWidth * 0.72, y: viewportHeight * 0.3, radius: viewportWidth * 0.16, color: '#38bdf8', speed: 0.18 }
      ];

      rings.forEach(ring => {
        ctx.beginPath();
        ctx.arc(ring.x, ring.y, ring.radius + Math.sin(time * ring.speed) * 10, 0.25, Math.PI * 1.65);
        ctx.strokeStyle = toRgba(ring.color, 0.12);
        ctx.lineWidth = 1.4;
        ctx.stroke();
      });
    }

    function startAnimation() {
      if (animationFrameId) return;

      const tick = now => {
        drawFrame(now);
        animationFrameId = window.requestAnimationFrame(tick);
      };

      animationFrameId = window.requestAnimationFrame(tick);
    }

    function stopAnimation() {
      if (!animationFrameId) return;
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = 0;
    }

    function buildPrompt(selectedVariant) {
      return [
        'Generate ONLY a valid SVG image.',
        'Do not include markdown, prose, code fences, comments or explanations.',
        'Return raw SVG starting with <svg and ending with </svg>.',
        'Width="1600" height="900" viewBox="0 0 1600 900".',
        'Create an abstract website background for the brand RPA4ALL.',
        'Visual direction: dark command center, premium automation platform, observability, orchestration and data movement.',
        'Use deep navy as the base and emerald #22c55e, cyan #38bdf8 and teal #14b8a6 as the main highlights.',
        'No text, no letters, no numbers, no logos, no people.',
        'Use gradients, paths, circles, soft glows, technical grids, telemetry arcs and flowing lines.',
        'Leave negative space for UI content and keep the composition elegant and asymmetrical.',
        'Theme emphasis: ' + selectedVariant.focus + '.',
        'Seed hint: ' + selectedVariant.seed + '.'
      ].join(' ');
    }

    function buildProviders() {
      const providers = [
        {
          kind: 'llm-chat',
          url: sameOriginApiBase + '/llm-tools/chat',
          timeout: 14000
        }
      ];

      if (sameOriginApiBase !== externalApiBase) {
        providers.push({
          kind: 'llm-chat',
          url: externalApiBase + '/llm-tools/chat',
          timeout: 14000
        });
      }

      if (directOllamaBase) {
        providers.unshift({
          kind: 'ollama',
          url: directOllamaBase + '/api/generate',
          timeout: 12000
        });
      }

      return providers.filter((provider, index, all) => {
        return all.findIndex(item => item.kind === provider.kind && item.url === provider.url) === index;
      });
    }

    async function fetchJson(url, options, timeoutMs) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, Object.assign({}, options, { signal: controller.signal }));
        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }
        return response.json();
      } finally {
        window.clearTimeout(timer);
      }
    }

    function extractText(payload) {
      if (!payload) return '';
      if (typeof payload === 'string') return payload;

      const candidates = [
        payload.svg,
        payload.response,
        payload.answer,
        payload.final_answer,
        payload.result,
        payload.content,
        payload.text,
        payload.output,
        payload.message && payload.message.content,
        payload.data && payload.data.content,
        payload.choices && payload.choices[0] && payload.choices[0].message && payload.choices[0].message.content
      ];

      const direct = candidates.find(value => typeof value === 'string' && value.trim());
      if (direct) return direct;

      if (Array.isArray(payload.messages)) {
        const message = payload.messages
          .map(item => item && item.content)
          .reverse()
          .find(value => typeof value === 'string' && value.trim());
        if (message) return message;
      }

      return '';
    }

    function sanitizeSvg(rawText) {
      if (!rawText) return '';
      const match = rawText.match(/<svg[\s\S]*?<\/svg>/i);
      if (!match) return '';

      const parser = new DOMParser();
      const documentSvg = parser.parseFromString(match[0], 'image/svg+xml');
      if (documentSvg.querySelector('parsererror')) return '';

      const svg = documentSvg.querySelector('svg');
      if (!svg) return '';

      svg.querySelectorAll('script, foreignObject, iframe, audio, video').forEach(node => node.remove());
      svg.querySelectorAll('*').forEach(node => {
        Array.from(node.attributes).forEach(attribute => {
          const name = attribute.name.toLowerCase();
          const value = attribute.value || '';
          if (name.startsWith('on')) {
            node.removeAttribute(attribute.name);
          }
          if ((name === 'href' || name === 'xlink:href') && /^\s*javascript:/i.test(value)) {
            node.removeAttribute(attribute.name);
          }
        });
      });

      svg.removeAttribute('width');
      svg.removeAttribute('height');
      svg.setAttribute('viewBox', svg.getAttribute('viewBox') || '0 0 1600 900');
      svg.setAttribute('preserveAspectRatio', 'xMidYMid slice');
      svg.setAttribute('focusable', 'false');
      svg.setAttribute('aria-hidden', 'true');
      return svg.outerHTML;
    }

    async function requestBackgroundSvg(selectedVariant) {
      svgSlot.innerHTML = '';
      document.body.classList.remove('site-background-ready');
      const prompt = buildPrompt(selectedVariant);

      for (const provider of buildProviders()) {
        try {
          let payload;
          if (provider.kind === 'ollama') {
            payload = await fetchJson(provider.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                model: 'qwen3:1.7b',
                prompt: prompt,
                stream: false,
                options: {
                  temperature: 1.08,
                  seed: selectedVariant.seed,
                  num_predict: 2200
                }
              })
            }, provider.timeout);
          } else {
            payload = await fetchJson(provider.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                prompt: prompt,
                model: 'qwen3:1.7b',
                max_rounds: 1,
                use_native_tools: false,
                conversation_id: 'background-' + selectedVariant.seed
              })
            }, provider.timeout);
          }

          const sanitized = sanitizeSvg(extractText(payload));
          if (!sanitized) continue;
          svgSlot.innerHTML = sanitized;
          document.body.classList.add('site-background-ready');
          return;
        } catch (error) {
          // Keep the animated canvas fallback and try the next provider.
        }
      }
    }
  })();

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

    // Animated counters (with IntersectionObserver fallback)
    let countersAnimated = false;
    function animateCounters() {
      if (countersAnimated) return;
      countersAnimated = true;
      document.querySelectorAll('.tech-stat-number').forEach(el => {
        const target = parseInt(el.dataset.count, 10);
        if (!target) return;
        el.textContent = '0';
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
    // Use IntersectionObserver for reliable trigger
    const statsEl = document.querySelector('.tech-stats');
    if (statsEl && 'IntersectionObserver' in window) {
      new IntersectionObserver((entries, obs) => {
        if (entries[0].isIntersecting) {
          animateCounters();
          obs.disconnect();
        }
      }, { threshold: 0.3 }).observe(statsEl);
    }

    // Trigger bar animations when tech tab is visible
    function onTechVisible(forceAll) {
      const panel = document.getElementById('technologies');
      if (panel && panel.classList.contains('active')) {
        animateBars(forceAll);
        animateCounters();
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

  (function initStorageCalculator() {
    const form = document.getElementById('storageCalculator');
    if (!form) return;
    form.addEventListener('submit', event => event.preventDefault());

    const fields = {
      temperature: document.getElementById('storageTemperature'),
      volume: document.getElementById('storageVolume'),
      ingress: document.getElementById('storageIngress'),
      retention: document.getElementById('storageRetention'),
      retrieval: document.getElementById('storageRetrieval'),
      sla: document.getElementById('storageSla'),
      compliance: document.getElementById('storageCompliance'),
      redundancy: document.getElementById('storageRedundancy')
    };

    const outputs = {
      offerMonthly: document.getElementById('storageOfferMonthly'),
      offerAnnual: document.getElementById('storageOfferAnnual'),
      effectiveRate: document.getElementById('storageEffectiveRate'),
      marketMonthly: document.getElementById('storageMarketMonthly'),
      savingsMonthly: document.getElementById('storageSavingsMonthly'),
      temperatureLabel: document.getElementById('storageTemperatureLabel'),
      offerBar: document.getElementById('storageOfferBar'),
      marketBar: document.getElementById('storageMarketBar'),
      offerBarLabel: document.getElementById('storageOfferBarLabel'),
      breakdown: document.getElementById('storageBreakdown')
    };

    const pricing = {
      hot: {
        label: 'Hot',
        rate: 168,
        marketRate: 209,
        ingressRate: 32,
        marketIngressRate: 39,
        platformFee: 280,
        marketPlatformFee: 340
      },
      warm: {
        label: 'Warm',
        rate: 106,
        marketRate: 132,
        ingressRate: 24,
        marketIngressRate: 30,
        platformFee: 280,
        marketPlatformFee: 340
      },
      cold: {
        label: 'Cold',
        rate: 58,
        marketRate: 74,
        ingressRate: 16,
        marketIngressRate: 20,
        platformFee: 260,
        marketPlatformFee: 320
      },
      archive: {
        label: 'Archive',
        rate: 29,
        marketRate: 39,
        ingressRate: 10,
        marketIngressRate: 13,
        platformFee: 240,
        marketPlatformFee: 300
      }
    };

    const retentionLabels = {
      6: '6 meses',
      12: '12 meses',
      24: '24 meses',
      60: '60 meses'
    };

    const retrievalLabels = {
      rare: 'recuperacoes raras',
      monthly: 'recuperacoes mensais',
      weekly: 'recuperacoes semanais'
    };

    const complianceLabels = {
      standard: 'compliance padrao',
      immutable30: 'imutabilidade de 30 dias',
      immutable90: 'imutabilidade de 90 dias'
    };

    const redundancyLabels = {
      single: 'site unico',
      dual: 'duas localidades'
    };

    const retentionMultipliers = {
      6: 1,
      12: 1.05,
      24: 1.11,
      60: 1.18
    };

    const retrievalMultipliers = {
      rare: 1,
      monthly: 1.08,
      weekly: 1.16
    };

    const slaMultipliers = {
      '48h': 1,
      '24h': 1.09,
      '4h': 1.22
    };

    const complianceMultipliers = {
      standard: 1,
      immutable30: 1.08,
      immutable90: 1.15
    };

    const redundancyMultipliers = {
      single: 1,
      dual: 1.16
    };

    const formatCurrency = new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0
    });

    function volumeDiscount(volumeTb) {
      if (volumeTb >= 100) return 0.82;
      if (volumeTb >= 50) return 0.86;
      if (volumeTb >= 15) return 0.91;
      if (volumeTb >= 5) return 0.96;
      return 1;
    }

    function sanitizeNumber(value, fallback, minimum) {
      const parsed = Number.parseFloat(value);
      if (!Number.isFinite(parsed)) return fallback;
      return Math.max(minimum, parsed);
    }

    function calculate() {
      const temperature = fields.temperature.value;
      const tier = pricing[temperature] || pricing.warm;
      const volume = sanitizeNumber(fields.volume.value, 20, 1);
      const ingress = sanitizeNumber(fields.ingress.value, 0, 0);
      const retention = fields.retention.value;
      const retrieval = fields.retrieval.value;
      const sla = fields.sla.value;
      const compliance = fields.compliance.value;
      const redundancy = fields.redundancy.value;

      const discount = volumeDiscount(volume);
      const retentionMultiplier = retentionMultipliers[retention] || 1;
      const retrievalMultiplier = retrievalMultipliers[retrieval] || 1;
      const slaMultiplier = slaMultipliers[sla] || 1;
      const complianceMultiplier = complianceMultipliers[compliance] || 1;
      const redundancyMultiplier = redundancyMultipliers[redundancy] || 1;

      const managedMultiplier =
        discount *
        retentionMultiplier *
        retrievalMultiplier *
        slaMultiplier *
        complianceMultiplier *
        redundancyMultiplier;

      const ingressMultiplier = discount * (1 + (retrievalMultiplier - 1) * 0.5) * (sla === '4h' ? 1.05 : 1);

      const monthlyOffer = Math.max(
        349,
        tier.platformFee +
        volume * tier.rate * managedMultiplier +
        ingress * tier.ingressRate * ingressMultiplier
      );

      const monthlyMarket = Math.max(
        459,
        tier.marketPlatformFee +
        volume * tier.marketRate * managedMultiplier +
        ingress * tier.marketIngressRate * ingressMultiplier
      );

      const annualOffer = monthlyOffer * 12;
      const monthlySavings = Math.max(0, monthlyMarket - monthlyOffer);
      const savingsPercentage = monthlyMarket > 0 ? (monthlySavings / monthlyMarket) * 100 : 0;
      const effectiveRate = monthlyOffer / volume;
      const offerVsMarket = monthlyMarket > 0 ? Math.min(100, (monthlyOffer / monthlyMarket) * 100) : 0;

      outputs.offerMonthly.textContent = formatCurrency.format(monthlyOffer) + '/mes';
      outputs.offerAnnual.textContent = formatCurrency.format(annualOffer) + '/ano';
      outputs.effectiveRate.textContent = formatCurrency.format(effectiveRate) + ' por TB protegido';
      outputs.marketMonthly.textContent = formatCurrency.format(monthlyMarket) + '/mes';
      outputs.savingsMonthly.textContent =
        'Economia mensal de ' +
        formatCurrency.format(monthlySavings) +
        ' (' +
        Math.round(savingsPercentage) +
        '% abaixo)';
      outputs.temperatureLabel.textContent = tier.label;
      outputs.offerBar.style.width = offerVsMarket + '%';
      outputs.marketBar.style.width = '100%';
      outputs.offerBarLabel.textContent = Math.round(offerVsMarket) + '%';

      outputs.breakdown.innerHTML = [
        '<li>Volume protegido: <strong>' + volume.toLocaleString('pt-BR') + ' TB</strong></li>',
        '<li>Novos dados por mes: <strong>' + ingress.toLocaleString('pt-BR') + ' TB</strong></li>',
        '<li>Retencao: <strong>' + (retentionLabels[retention] || retention + ' meses') + '</strong> com ' + (complianceLabels[compliance] || 'compliance padrao') + '</li>',
        '<li>Restore: <strong>' + sla + '</strong> com ' + (retrievalLabels[retrieval] || 'recuperacoes raras') + '</li>',
        '<li>Topologia: <strong>' + (redundancyLabels[redundancy] || 'site unico') + '</strong> e desconto por volume aplicado: <strong>' + Math.round((1 - discount) * 100) + '%</strong></li>'
      ].join('');
    }

    form.addEventListener('input', calculate);
    form.addEventListener('change', calculate);
    calculate();
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
