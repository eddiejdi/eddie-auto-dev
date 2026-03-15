document.addEventListener('DOMContentLoaded', function () {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');

  if (tabs.length && panels.length) {
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

    document.addEventListener('keyup', e => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const arr = Array.from(tabs);
        const idx = arr.findIndex(t => t.classList.contains('active'));
        const next = e.key === 'ArrowRight' ? (idx + 1) % arr.length : (idx - 1 + arr.length) % arr.length;
        if (arr[next]) arr[next].click();
      }
    });
  }

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

  const storageQuoteStorageKey = 'rpa4all_storage_quote_v1';
  const resellerQuoteStorageKey = 'rpa4all_reseller_quote_v1';
  const storageRequestStorageKey = 'rpa4all_storage_request_v1';
  const storageQuoteFormatter = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0
  });

  const storagePricing = {
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

  const storageRetentionLabels = {
    6: '6 meses',
    12: '12 meses',
    24: '24 meses',
    60: '60 meses'
  };

  const storageRetrievalLabels = {
    rare: 'recuperacoes raras',
    monthly: 'recuperacoes mensais',
    weekly: 'recuperacoes semanais'
  };

  const storageComplianceLabels = {
    standard: 'compliance padrao',
    immutable30: 'imutabilidade de 30 dias',
    immutable90: 'imutabilidade de 90 dias'
  };

  const storageRedundancyLabels = {
    single: 'site unico',
    dual: 'duas localidades'
  };

  const storageRetentionMultipliers = {
    6: 1,
    12: 1.05,
    24: 1.11,
    60: 1.18
  };

  const storageRetrievalMultipliers = {
    rare: 1,
    monthly: 1.08,
    weekly: 1.16
  };

  const storageSlaMultipliers = {
    '48h': 1,
    '24h': 1.09,
    '4h': 1.22
  };

  const storageComplianceMultipliers = {
    standard: 1,
    immutable30: 1.08,
    immutable90: 1.15
  };

  const storageRedundancyMultipliers = {
    single: 1,
    dual: 1.16
  };

  function safeJsonSet(key, payload) {
    try {
      window.localStorage.setItem(key, JSON.stringify(payload));
    } catch (error) {
      // ignore storage failures
    }
  }

  function safeJsonGet(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function sanitizeStorageNumber(value, fallback, minimum) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.max(minimum, parsed);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function getStorageVolumeDiscount(volumeTb) {
    if (volumeTb >= 100) return 0.82;
    if (volumeTb >= 50) return 0.86;
    if (volumeTb >= 15) return 0.91;
    if (volumeTb >= 5) return 0.96;
    return 1;
  }

  function calculateStorageQuote(input) {
    const temperature = input.temperature;
    const tier = storagePricing[temperature] || storagePricing.warm;
    const volume = sanitizeStorageNumber(input.volume, 20, 1);
    const ingress = sanitizeStorageNumber(input.ingress, 0, 0);
    const retention = String(input.retention || '12');
    const retrieval = input.retrieval || 'rare';
    const sla = input.sla || '24h';
    const compliance = input.compliance || 'standard';
    const redundancy = input.redundancy || 'single';

    const discount = getStorageVolumeDiscount(volume);
    const retentionMultiplier = storageRetentionMultipliers[retention] || 1;
    const retrievalMultiplier = storageRetrievalMultipliers[retrieval] || 1;
    const slaMultiplier = storageSlaMultipliers[sla] || 1;
    const complianceMultiplier = storageComplianceMultipliers[compliance] || 1;
    const redundancyMultiplier = storageRedundancyMultipliers[redundancy] || 1;

    const managedMultiplier =
      discount *
      retentionMultiplier *
      retrievalMultiplier *
      slaMultiplier *
      complianceMultiplier *
      redundancyMultiplier;

    const ingressMultiplier =
      discount *
      (1 + (retrievalMultiplier - 1) * 0.5) *
      (sla === '4h' ? 1.05 : 1);

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

    return {
      temperature: temperature,
      tier: tier,
      volume: volume,
      ingress: ingress,
      retention: retention,
      retrieval: retrieval,
      sla: sla,
      compliance: compliance,
      redundancy: redundancy,
      discount: discount,
      monthlyOffer: monthlyOffer,
      monthlyMarket: monthlyMarket,
      annualOffer: annualOffer,
      monthlySavings: monthlySavings,
      savingsPercentage: savingsPercentage,
      effectiveRate: effectiveRate,
      offerVsMarket: offerVsMarket,
      labels: {
        retention: storageRetentionLabels[retention] || retention + ' meses',
        retrieval: storageRetrievalLabels[retrieval] || 'recuperacoes raras',
        compliance: storageComplianceLabels[compliance] || 'compliance padrao',
        redundancy: storageRedundancyLabels[redundancy] || 'site unico'
      }
    };
  }

  function buildStorageBreakdownItems(quote) {
    return [
      '<li>Volume protegido: <strong>' + quote.volume.toLocaleString('pt-BR') + ' TB</strong></li>',
      '<li>Novos dados por mes: <strong>' + quote.ingress.toLocaleString('pt-BR') + ' TB</strong></li>',
      '<li>Retencao: <strong>' + quote.labels.retention + '</strong> com ' + quote.labels.compliance + '</li>',
      '<li>Restore: <strong>' + quote.sla + '</strong> com ' + quote.labels.retrieval + '</li>',
      '<li>Topologia: <strong>' + quote.labels.redundancy + '</strong> e desconto por volume aplicado: <strong>' + Math.round((1 - quote.discount) * 100) + '%</strong></li>'
    ];
  }

  function renderStorageQuote(outputs, quote) {
    outputs.offerMonthly.textContent = storageQuoteFormatter.format(quote.monthlyOffer) + '/mes';
    outputs.offerAnnual.textContent = storageQuoteFormatter.format(quote.annualOffer) + '/ano';
    outputs.effectiveRate.textContent = storageQuoteFormatter.format(quote.effectiveRate) + ' por TB protegido';
    outputs.marketMonthly.textContent = storageQuoteFormatter.format(quote.monthlyMarket) + '/mes';
    outputs.savingsMonthly.textContent =
      'Economia mensal de ' +
      storageQuoteFormatter.format(quote.monthlySavings) +
      ' (' +
      Math.round(quote.savingsPercentage) +
      '% abaixo)';
    outputs.temperatureLabel.textContent = quote.tier.label;
    outputs.offerBar.style.width = quote.offerVsMarket + '%';
    outputs.marketBar.style.width = '100%';
    outputs.offerBarLabel.textContent = Math.round(quote.offerVsMarket) + '%';
    outputs.breakdown.innerHTML = buildStorageBreakdownItems(quote).join('');
  }

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

    function calculate() {
      const snapshot = {
        temperature: fields.temperature.value,
        volume: fields.volume.value,
        ingress: fields.ingress.value,
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value
      };

      const quote = calculateStorageQuote(snapshot);
      renderStorageQuote(outputs, quote);
      safeJsonSet(storageQuoteStorageKey, snapshot);
    }

    form.addEventListener('input', calculate);
    form.addEventListener('change', calculate);
    calculate();
  })();

  (function initResellerCalculator() {
    const form = document.getElementById('resellerCalculator');
    if (!form) return;
    form.addEventListener('submit', event => event.preventDefault());

    const fields = {
      resellerCompany: document.getElementById('resellerCompany'),
      resellerContact: document.getElementById('resellerContact'),
      resellerEmail: document.getElementById('resellerEmail'),
      customer: document.getElementById('resellerCustomer'),
      partnerModel: document.getElementById('resellerModel'),
      billingModel: document.getElementById('resellerBilling'),
      temperature: document.getElementById('resellerTemperature'),
      volume: document.getElementById('resellerVolume'),
      ingress: document.getElementById('resellerIngress'),
      retention: document.getElementById('resellerRetention'),
      retrieval: document.getElementById('resellerRetrieval'),
      sla: document.getElementById('resellerSla'),
      compliance: document.getElementById('resellerCompliance'),
      redundancy: document.getElementById('resellerRedundancy'),
      contractTerm: document.getElementById('resellerTerm')
    };

    const outputs = {
      offerMonthly: document.getElementById('resellerOfferMonthly'),
      temperatureLabel: document.getElementById('resellerTemperatureLabel'),
      commissionMonthly: document.getElementById('resellerCommissionMonthly'),
      commissionRate: document.getElementById('resellerCommissionRate'),
      contractValue: document.getElementById('resellerContractValue'),
      contractTermLabel: document.getElementById('resellerContractTermLabel'),
      projectedCommission: document.getElementById('resellerProjectedCommission'),
      billingLabel: document.getElementById('resellerBillingLabel'),
      breachPenalty: document.getElementById('resellerBreachPenalty'),
      exitTerms: document.getElementById('resellerExitTerms'),
      breakdown: document.getElementById('resellerBreakdown'),
      preview: document.getElementById('resellerContractPreview'),
      metaPartner: document.getElementById('resellerContractMetaPartner'),
      metaCustomer: document.getElementById('resellerContractMetaCustomer'),
      metaTerm: document.getElementById('resellerContractMetaTerm')
    };

    const syncButton = document.getElementById('resellerSyncFromStorage');
    const copyButton = document.getElementById('resellerContractCopy');

    const partnerLabels = {
      referral: 'Indicacao comercial',
      managed: 'Revenda gerenciada',
      white_label: 'White label'
    };

    const billingLabels = {
      monthly: 'faturamento mensal',
      quarterly: 'faturamento trimestral',
      annual: 'faturamento anual antecipado'
    };

    const billingFactors = {
      monthly: 1,
      quarterly: 0.985,
      annual: 0.96
    };

    function formatPercent(decimalValue) {
      return (decimalValue * 100).toFixed(1).replace('.', ',') + '%';
    }

    function getContractTermLabel(termMonths) {
      return termMonths + ' meses';
    }

    function getNoticeDays(partnerModel) {
      if (partnerModel === 'white_label') return 60;
      if (partnerModel === 'managed') return 45;
      return 30;
    }

    function getCommissionRate(quote, partnerModel, termMonths, billingModel) {
      let rate = partnerModel === 'white_label'
        ? 0.18
        : partnerModel === 'managed'
          ? 0.14
          : 0.10;

      if (quote.volume >= 80) rate += 0.03;
      else if (quote.volume >= 30) rate += 0.02;
      else if (quote.volume >= 10) rate += 0.01;

      if (quote.redundancy === 'dual') rate += 0.01;
      if (termMonths >= 24) rate += 0.01;
      if (termMonths >= 36) rate += 0.01;
      if (quote.temperature === 'hot') rate += 0.005;
      if (quote.temperature === 'archive') rate -= 0.005;
      if (billingModel === 'annual') rate += 0.005;
      if (billingModel === 'quarterly') rate += 0.0025;

      return Math.min(0.24, Math.max(0.10, rate));
    }

    function buildContractPreview(payload) {
      const partnerName = escapeHtml(payload.partnerName);
      const partnerContact = escapeHtml(payload.partnerContact);
      const partnerEmail = escapeHtml(payload.partnerEmail);
      const partnerModelLabel = escapeHtml(payload.partnerModelLabel);
      const customerName = escapeHtml(payload.customerName);
      const billingLabel = escapeHtml(payload.billingLabel);
      const termLabel = escapeHtml(payload.termLabel);

      return [
        '<h5>Contrato Simulado de Revenda de Storage Gerenciado</h5>',
        '<p><strong>Partes.</strong> De um lado, <strong>RPA4ALL</strong>, como operadora da oferta. De outro, <strong>' + partnerName + '</strong>, representada por <strong>' + partnerContact + '</strong>, email <strong>' + partnerEmail + '</strong>, na qualidade de parceira comercial do modelo <strong>' + partnerModelLabel + '</strong>.</p>',
        '<div class="reseller-contract-grid">',
        '<div><strong>Cliente final</strong><p>' + customerName + '</p></div>',
        '<div><strong>Oferta simulada</strong><p>' + payload.quote.tier.label + ' | ' + payload.quote.volume.toLocaleString('pt-BR') + ' TB | ' + payload.quote.labels.retention + '</p></div>',
        '<div><strong>Ticket mensal equivalente</strong><p>' + storageQuoteFormatter.format(payload.customerMonthly) + '</p></div>',
        '<div><strong>Comissao do parceiro</strong><p>' + formatPercent(payload.commissionRate) + ' recorrentes sobre receita elegivel</p></div>',
        '</div>',
        '<h6>1. Objeto</h6>',
        '<p>Este instrumento simula as condicoes comerciais para revenda da oferta de storage gerenciado da RPA4ALL para a oportunidade <strong>' + customerName + '</strong>, contemplando temperatura <strong>' + payload.quote.tier.label + '</strong>, volume protegido de <strong>' + payload.quote.volume.toLocaleString('pt-BR') + ' TB</strong>, ingresso mensal de <strong>' + payload.quote.ingress.toLocaleString('pt-BR') + ' TB</strong>, SLA de restore <strong>' + payload.quote.sla + '</strong>, ' + payload.quote.labels.compliance + ' e topologia em <strong>' + payload.quote.labels.redundancy + '</strong>.</p>',
        '<h6>2. Oferta comercial</h6>',
        '<p>Para fins de proposta, o ticket equivalente do cliente final fica estimado em <strong>' + storageQuoteFormatter.format(payload.customerMonthly) + ' por mes</strong>, com valor contratual projetado de <strong>' + storageQuoteFormatter.format(payload.contractValue) + '</strong> ao longo de <strong>' + termLabel + '</strong>, considerando <strong>' + billingLabel + '</strong>.</p>',
        '<ul>',
        '<li>Referencia de mercado equivalente: ' + storageQuoteFormatter.format(payload.quote.monthlyMarket) + ' por mes.</li>',
        '<li>Economia potencial frente ao benchmark: ' + storageQuoteFormatter.format(payload.quote.monthlySavings) + ' por mes.</li>',
        '<li>Faturamento contratual considerado para a simulação: ' + storageQuoteFormatter.format(payload.contractValue) + '.</li>',
        '</ul>',
        '<h6>3. Comissao e elegibilidade</h6>',
        '<p>A parceira faria jus a comissao recorrente de <strong>' + formatPercent(payload.commissionRate) + '</strong> sobre a receita efetivamente recebida pela RPA4ALL no escopo desta conta, o que representa uma projeção de <strong>' + storageQuoteFormatter.format(payload.monthlyCommission) + ' por mes</strong> e <strong>' + storageQuoteFormatter.format(payload.projectedCommission) + '</strong> ao longo da vigencia simulada.</p>',
        '<p>Pagamentos de comissao pressupõem contrato ativo, cliente adimplente, faturamento elegivel e inexistencia de bypass comercial ou disputa de titularidade do lead.</p>',
        '<h6>4. Saida honrosa e desist&ecirc;ncia</h6>',
        '<p>As partes podem encerrar a parceria desta oportunidade por meio de <strong>saida honrosa</strong>, mediante aviso previo escrito de <strong>' + payload.noticeDays + ' dias</strong>, sem multa rescisoria, desde que haja transicao ordenada, quitacao de valores vencidos, devolucao de materiais confidenciais e preservacao do atendimento ao cliente final durante o periodo de handoff.</p>',
        '<p>Se houver <strong>desistencia do cliente final antes da ativacao</strong>, a oportunidade pode ser encerrada sem penalidade comercial adicional, ficando apenas os custos aprovados e irrecuperaveis de sizing, onboarding ou reserva de capacidade limitados a <strong>' + storageQuoteFormatter.format(payload.desistenceExposure) + '</strong>, quando expressamente autorizados.</p>',
        '<h6>5. Quebra contratual</h6>',
        '<p>Caracteriza quebra contratual, entre outros, o desvio de oportunidade, a omissao deliberada de informacoes materiais, o compartilhamento indevido de proposta, a violacao de confidencialidade, a oferta direta ao cliente final sem anuencia da RPA4ALL ou inadimplencia superior a 30 dias em valores devidos no ambito desta parceria.</p>',
        '<p>Nessas hipoteses, a RPA4ALL podera rescindir imediatamente este instrumento e aplicar penalidade comercial estimada em <strong>' + storageQuoteFormatter.format(payload.breachPenalty) + '</strong>, sem prejuizo da cobranca de perdas e danos adicionais comprovados.</p>',
        '<h6>6. Observacoes finais</h6>',
        '<p>Este texto tem natureza de <strong>simulacao comercial</strong> e serve como base de negociacao. A minuta final deve passar por revisao juridica, validacao de compliance e aceite formal das partes antes da assinatura.</p>'
      ].join('');
    }

    function calculate() {
      const termMonths = Number.parseInt(fields.contractTerm.value, 10) || 12;
      const partnerModel = fields.partnerModel.value;
      const billingModel = fields.billingModel.value;
      const baseQuote = calculateStorageQuote({
        temperature: fields.temperature.value,
        volume: fields.volume.value,
        ingress: fields.ingress.value,
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value
      });

      const billingFactor = billingFactors[billingModel] || 1;
      const customerMonthly = Math.max(349, baseQuote.monthlyOffer * billingFactor);
      const contractValue = customerMonthly * termMonths;
      const commissionRate = getCommissionRate(baseQuote, partnerModel, termMonths, billingModel);
      const monthlyCommission = customerMonthly * commissionRate;
      const projectedCommission = monthlyCommission * termMonths;
      const noticeDays = getNoticeDays(partnerModel);
      const desistenceExposure = Math.max(900, customerMonthly * 0.35);
      const breachPenalty = Math.max(contractValue * 0.1, monthlyCommission * 2);
      const termLabel = getContractTermLabel(termMonths);
      const billingLabel = billingLabels[billingModel] || 'faturamento mensal';
      const partnerName = (fields.resellerCompany.value || '').trim() || 'Parceiro Canal RPA4ALL';
      const partnerContact = (fields.resellerContact.value || '').trim() || 'Responsavel comercial';
      const partnerEmail = (fields.resellerEmail.value || '').trim() || 'canal@parceiro.com.br';
      const customerName = (fields.customer.value || '').trim() || 'Conta estrategica em qualificacao';
      const snapshot = {
        resellerCompany: fields.resellerCompany.value,
        resellerContact: fields.resellerContact.value,
        resellerEmail: fields.resellerEmail.value,
        customer: fields.customer.value,
        partnerModel: partnerModel,
        billingModel: billingModel,
        temperature: fields.temperature.value,
        volume: fields.volume.value,
        ingress: fields.ingress.value,
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value,
        contractTerm: fields.contractTerm.value
      };

      outputs.offerMonthly.textContent = storageQuoteFormatter.format(customerMonthly) + '/mes';
      outputs.temperatureLabel.textContent = baseQuote.tier.label;
      outputs.commissionMonthly.textContent = storageQuoteFormatter.format(monthlyCommission) + '/mes';
      outputs.commissionRate.textContent = formatPercent(commissionRate) + ' sobre a receita elegivel';
      outputs.contractValue.textContent = storageQuoteFormatter.format(contractValue);
      outputs.contractTermLabel.textContent = 'vigencia de ' + termLabel;
      outputs.projectedCommission.textContent = storageQuoteFormatter.format(projectedCommission);
      outputs.billingLabel.textContent = billingLabel;
      outputs.breachPenalty.textContent = storageQuoteFormatter.format(breachPenalty);
      outputs.exitTerms.textContent = 'saida honrosa com aviso de ' + noticeDays + ' dias';
      outputs.breakdown.innerHTML = [
        '<li>Parceiro: <strong>' + partnerLabels[partnerModel] + '</strong> para a conta <strong>' + customerName + '</strong>.</li>',
        '<li>Oferta ao cliente final: <strong>' + storageQuoteFormatter.format(customerMonthly) + '/mes</strong> em ' + baseQuote.tier.label + ' com ' + baseQuote.labels.redundancy + '.</li>',
        '<li>Comissao recorrente simulada: <strong>' + formatPercent(commissionRate) + '</strong>, projetando ' + storageQuoteFormatter.format(projectedCommission) + ' em ' + termLabel + '.</li>',
        '<li>Desistencia pre-ativacao: exposicao maxima estimada em <strong>' + storageQuoteFormatter.format(desistenceExposure) + '</strong> para sizing e onboarding aprovados.</li>',
        '<li>Quebra contratual: penalidade comercial base de <strong>' + storageQuoteFormatter.format(breachPenalty) + '</strong>.</li>'
      ].join('');

      outputs.metaPartner.textContent = 'Parceiro: ' + partnerName;
      outputs.metaCustomer.textContent = 'Cliente final: ' + customerName;
      outputs.metaTerm.textContent = 'Vigencia: ' + termLabel;
      outputs.preview.innerHTML = buildContractPreview({
        partnerName: partnerName,
        partnerContact: partnerContact,
        partnerEmail: partnerEmail,
        partnerModelLabel: partnerLabels[partnerModel] || 'Revenda gerenciada',
        customerName: customerName,
        quote: baseQuote,
        customerMonthly: customerMonthly,
        contractValue: contractValue,
        commissionRate: commissionRate,
        monthlyCommission: monthlyCommission,
        projectedCommission: projectedCommission,
        noticeDays: noticeDays,
        desistenceExposure: desistenceExposure,
        breachPenalty: breachPenalty,
        billingLabel: billingLabel,
        termLabel: termLabel
      });
      safeJsonSet(resellerQuoteStorageKey, snapshot);
    }

    if (syncButton) {
      syncButton.addEventListener('click', () => {
        const snapshot = safeJsonGet(storageQuoteStorageKey, null);
        if (!snapshot) return;
        fields.temperature.value = snapshot.temperature || fields.temperature.value;
        fields.volume.value = snapshot.volume || fields.volume.value;
        fields.ingress.value = snapshot.ingress || fields.ingress.value;
        fields.retention.value = snapshot.retention || fields.retention.value;
        fields.retrieval.value = snapshot.retrieval || fields.retrieval.value;
        fields.sla.value = snapshot.sla || fields.sla.value;
        fields.compliance.value = snapshot.compliance || fields.compliance.value;
        fields.redundancy.value = snapshot.redundancy || fields.redundancy.value;
        calculate();
      });
    }

    const savedResellerSnapshot = safeJsonGet(resellerQuoteStorageKey, null);
    if (savedResellerSnapshot) {
      Object.entries(savedResellerSnapshot).forEach(([key, value]) => {
        const field = fields[key];
        if (field && value != null) {
          field.value = value;
        }
      });
    }

    if (copyButton) {
      copyButton.addEventListener('click', async () => {
        if (!outputs.preview) return;
        const originalText = copyButton.textContent;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(outputs.preview.innerText.trim());
            copyButton.textContent = 'Contrato copiado';
          } else {
            copyButton.textContent = 'Copie manualmente';
          }
        } catch (error) {
          copyButton.textContent = 'Copie manualmente';
        }

        window.setTimeout(() => {
          copyButton.textContent = originalText;
        }, 1800);
      });
    }

    form.addEventListener('input', calculate);
    form.addEventListener('change', calculate);
    calculate();
  })();

  (function initStorageRequestPage() {
    const form = document.getElementById('storageRequestForm');
    if (!form) return;
    form.addEventListener('submit', event => event.preventDefault());

    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode') === 'space' ? 'space' : 'sizing';

    const fields = {
      company: document.getElementById('requestCompany'),
      legalName: document.getElementById('requestLegalName'),
      contact: document.getElementById('requestContact'),
      role: document.getElementById('requestRole'),
      email: document.getElementById('requestEmail'),
      phone: document.getElementById('requestPhone'),
      project: document.getElementById('requestProject'),
      temperature: document.getElementById('requestTemperature'),
      volume: document.getElementById('requestVolume'),
      ingress: document.getElementById('requestIngress'),
      retention: document.getElementById('requestRetention'),
      retrieval: document.getElementById('requestRetrieval'),
      sla: document.getElementById('requestSla'),
      compliance: document.getElementById('requestCompliance'),
      redundancy: document.getElementById('requestRedundancy'),
      billing: document.getElementById('requestBilling'),
      term: document.getElementById('requestTerm'),
      startDate: document.getElementById('requestStartDate'),
      city: document.getElementById('requestCity'),
      state: document.getElementById('requestState'),
      notes: document.getElementById('requestNotes')
    };

    const outputs = {
      modeEyebrow: document.getElementById('requestModeEyebrow'),
      pageTitle: document.getElementById('requestPageTitle'),
      pageLead: document.getElementById('requestPageLead'),
      summaryTitle: document.getElementById('requestSummaryTitle'),
      summaryNote: document.getElementById('requestSummaryNote'),
      resultsKicker: document.getElementById('requestResultsKicker'),
      offerMonthly: document.getElementById('requestOfferMonthly'),
      monthlyRecurring: document.getElementById('requestMonthlyRecurring'),
      billingLabel: document.getElementById('requestBillingLabel'),
      setupFee: document.getElementById('requestSetupFee'),
      startLabel: document.getElementById('requestStartLabel'),
      contractValue: document.getElementById('requestContractValue'),
      contractTermLabel: document.getElementById('requestContractTermLabel'),
      breachPenalty: document.getElementById('requestBreachPenalty'),
      exitTerms: document.getElementById('requestExitTerms'),
      temperatureLabel: document.getElementById('requestTemperatureLabel'),
      breakdown: document.getElementById('requestBreakdown'),
      contractTitle: document.getElementById('requestContractTitle'),
      contractMetaCustomer: document.getElementById('requestContractMetaCustomer'),
      contractMetaProject: document.getElementById('requestContractMetaProject'),
      contractMetaStart: document.getElementById('requestContractMetaStart'),
      contractPreview: document.getElementById('requestContractPreview')
    };

    const syncButton = document.getElementById('requestSyncFromStorage');
    const copyButton = document.getElementById('requestContractCopy');
    const provisionButton = document.getElementById('requestProvisionAccessButton');
    const provisionHint = document.getElementById('requestProvisionHint');
    const provisionStatus = document.getElementById('requestProvisionStatus');
    let latestRequestState = null;

    const modeContent = {
      sizing: {
        eyebrow: 'Solicitação de sizing',
        title: 'Preencha os dados da operação para gerar a minuta comercial inicial.',
        lead: 'Use esta etapa para estruturar capacidade, retenção, restore e premissas contratuais antes da proposta formal.',
        summaryTitle: 'Sizing consultivo com base contratual na mesma tela.',
        summaryNote: 'Ideal para qualificar a operação, validar premissas e sair com texto inicial para revisão comercial.',
        resultsKicker: 'Sizing estimado',
        contractTitle: 'Minuta comercial de sizing e storage',
        actionLabel: 'Solicitar sizing',
        actionHint: 'Ao confirmar, geramos um acesso no portal e enviamos as credenciais por email.'
      },
      space: {
        eyebrow: 'Solicitação de espaço',
        title: 'Reserve capacidade de storage e gere a minuta inicial da contratação.',
        lead: 'Use este fluxo para pedir espaço protegido, formalizar janela de ativação e gerar um contrato-base com os dados do cliente.',
        summaryTitle: 'Reserva de capacidade com minuta inicial pronta para negociação.',
        summaryNote: 'Ideal para operações que já conhecem o volume e querem acelerar o fechamento comercial sem depender de email.',
        resultsKicker: 'Espaço solicitado',
        contractTitle: 'Minuta comercial de reserva de capacidade',
        actionLabel: 'Solicitar espaço',
        actionHint: 'Ao confirmar, reservamos o fluxo comercial, criamos o acesso no portal e enviamos as credenciais por email.'
      }
    };

    const billingLabels = {
      monthly: 'faturamento mensal',
      quarterly: 'faturamento trimestral',
      annual: 'faturamento anual antecipado'
    };

    const billingFactors = {
      monthly: 1,
      quarterly: 0.985,
      annual: 0.96
    };

    function formatDateDisplay(dateValue) {
      if (!dateValue) return 'a definir';
      const parts = String(dateValue).split('-');
      if (parts.length !== 3) return escapeHtml(dateValue);
      return parts[2] + '/' + parts[1] + '/' + parts[0];
    }

    function getNoticeDays(quote, termMonths) {
      let days = mode === 'space' ? 30 : 20;
      if (quote.temperature === 'hot') days += 10;
      if (quote.redundancy === 'dual') days += 10;
      if (termMonths >= 24) days += 5;
      return days;
    }

    function getSetupFee(quote) {
      let fee = mode === 'space' ? 1400 : 950;
      fee += quote.volume * 18;
      fee += quote.ingress * 42;
      if (quote.sla === '4h') fee += 750;
      if (quote.compliance !== 'standard') fee += 420;
      if (quote.redundancy === 'dual') fee += 580;
      return Math.round(fee);
    }

    function setProvisionStatus(message, tone) {
      if (!provisionStatus) return;
      provisionStatus.textContent = message || '';
      provisionStatus.classList.remove('is-success', 'is-error', 'is-pending');
      if (tone === 'success') {
        provisionStatus.classList.add('is-success');
      } else if (tone === 'error') {
        provisionStatus.classList.add('is-error');
      } else if (tone === 'pending') {
        provisionStatus.classList.add('is-pending');
      }
    }

    function buildRequestState() {
      const quote = calculateStorageQuote({
        temperature: fields.temperature.value,
        volume: fields.volume.value,
        ingress: fields.ingress.value,
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value
      });

      const termMonths = Number.parseInt(fields.term.value, 10) || 12;
      const billing = fields.billing.value;
      const billingFactor = billingFactors[billing] || 1;
      const monthlyService = Math.max(349, quote.monthlyOffer * billingFactor);
      const setupFee = getSetupFee(quote);
      const contractValue = monthlyService * termMonths + setupFee;
      const noticeDays = getNoticeDays(quote, termMonths);
      const breachPenalty = Math.max(contractValue * 0.08, monthlyService * 2);
      const termLabel = termMonths + ' meses';
      const billingLabel = billingLabels[billing] || 'faturamento mensal';
      const startDate = formatDateDisplay(fields.startDate.value);
      const company = (fields.company.value || '').trim() || 'Empresa interessada';
      const legalName = (fields.legalName.value || '').trim() || company;
      const contact = (fields.contact.value || '').trim() || 'Responsável da operação';
      const role = (fields.role.value || '').trim() || 'Tecnologia / Operações';
      const email = (fields.email.value || '').trim() || 'contato@empresa.com.br';
      const phone = (fields.phone.value || '').trim() || '+55 11 99999-9999';
      const project = (fields.project.value || '').trim() || 'Projeto de storage corporativo';
      const city = (fields.city.value || '').trim() || 'São Paulo';
      const state = (fields.state.value || '').trim().toUpperCase() || 'SP';
      const notes = (fields.notes.value || '').trim();

      return {
        mode: mode,
        quote: quote,
        termMonths: termMonths,
        billing: billing,
        billingLabel: billingLabel,
        monthlyService: monthlyService,
        setupFee: setupFee,
        contractValue: contractValue,
        noticeDays: noticeDays,
        breachPenalty: breachPenalty,
        termLabel: termLabel,
        startDate: startDate,
        company: company,
        legalName: legalName,
        contact: contact,
        role: role,
        email: email,
        phone: phone,
        project: project,
        city: city,
        state: state,
        notes: notes,
        startDateRaw: fields.startDate.value || '',
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value
      };
    }

    function validateProvisionRequest(state) {
      const email = String(state.email || '').trim().toLowerCase();
      if (!state.company || state.company === 'Empresa interessada') {
        return 'Preencha o nome real da empresa antes de solicitar o sizing.';
      }
      if (!state.contact || state.contact === 'Nome do responsável' || state.contact === 'Responsável da operação') {
        return 'Informe o responsável que receberá as credenciais.';
      }
      if (!state.project || state.project === 'Projeto de storage corporativo') {
        return 'Descreva o projeto antes de solicitar o sizing.';
      }
      if (!email || email === 'contato@empresa.com.br' || /@empresa\.com(\.[a-z]{2,})?$/i.test(email)) {
        return 'Informe um email corporativo real para receber o acesso.';
      }
      return '';
    }

    function buildProvisionPayload(state) {
      return {
        mode: state.mode,
        company: state.company,
        legal_name: state.legalName,
        contact: state.contact,
        role: state.role,
        email: state.email,
        phone: state.phone,
        project: state.project,
        temperature: state.quote.temperature,
        volume: Number(state.quote.volume.toFixed(2)),
        ingress: Number(state.quote.ingress.toFixed(2)),
        retention: state.retention,
        retrieval: state.retrieval,
        sla: state.sla,
        compliance: state.compliance,
        redundancy: state.redundancy,
        billing: state.billing,
        term: state.termMonths,
        start_date: state.startDateRaw || null,
        city: state.city,
        state: state.state,
        notes: state.notes,
        monthly_service: Math.round(state.monthlyService),
        setup_fee: Math.round(state.setupFee),
        contract_value: Math.round(state.contractValue),
        notice_days: state.noticeDays,
        breach_penalty: Math.round(state.breachPenalty)
      };
    }

    async function postProvisionRequest(payload) {
      const primaryEndpoint = window.location.origin + '/agents-api/storage/request-access';
      const fallbackEndpoint = 'https://api.rpa4all.com/agents-api/storage/request-access';
      const endpoints = [primaryEndpoint];

      if (fallbackEndpoint !== primaryEndpoint) {
        endpoints.push(fallbackEndpoint);
      }

      let lastError = new Error('Não foi possível conectar ao serviço de provisionamento.');

      for (const endpoint of endpoints) {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 18000);
        try {
          const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
          });
          let data = {};
          try {
            data = await response.json();
          } catch (error) {
            data = {};
          }

          if (!response.ok) {
            const detail = typeof data.detail === 'string'
              ? data.detail
              : ('Falha ao provisionar o acesso (' + response.status + ').');
            throw new Error(detail);
          }

          return data;
        } catch (error) {
          lastError = error;
        } finally {
          window.clearTimeout(timer);
        }
      }

      throw lastError;
    }

    function buildRequestContract(payload) {
      const company = escapeHtml(payload.company);
      const legalName = escapeHtml(payload.legalName);
      const contact = escapeHtml(payload.contact);
      const role = escapeHtml(payload.role);
      const email = escapeHtml(payload.email);
      const phone = escapeHtml(payload.phone);
      const project = escapeHtml(payload.project);
      const city = escapeHtml(payload.city);
      const state = escapeHtml(payload.state);
      const notes = escapeHtml(payload.notes);
      const startDate = escapeHtml(payload.startDate);
      const billingLabel = escapeHtml(payload.billingLabel);
      const termLabel = escapeHtml(payload.termLabel);
      const modeLabel = mode === 'space' ? 'reserva de capacidade' : 'sizing consultivo';

      return [
        '<h5>' + outputs.contractTitle.textContent + '</h5>',
        '<p><strong>Partes.</strong> De um lado, <strong>RPA4ALL</strong>, como operadora da oferta de storage gerenciado. De outro, <strong>' + company + '</strong> (' + legalName + '), representada por <strong>' + contact + '</strong>, <strong>' + role + '</strong>, email <strong>' + email + '</strong> e telefone <strong>' + phone + '</strong>.</p>',
        '<div class="reseller-contract-grid">',
        '<div><strong>Projeto</strong><p>' + project + '</p></div>',
        '<div><strong>Modalidade</strong><p>' + modeLabel + '</p></div>',
        '<div><strong>Localidade</strong><p>' + city + '/' + state + '</p></div>',
        '<div><strong>Início pretendido</strong><p>' + startDate + '</p></div>',
        '</div>',
        '<h6>1. Objeto</h6>',
        '<p>Esta minuta registra a intenção comercial de contratação da oferta de storage gerenciado da RPA4ALL para o projeto <strong>' + project + '</strong>, contemplando temperatura <strong>' + payload.quote.tier.label + '</strong>, volume protegido de <strong>' + payload.quote.volume.toLocaleString('pt-BR') + ' TB</strong>, ingresso mensal de <strong>' + payload.quote.ingress.toLocaleString('pt-BR') + ' TB</strong>, retenção de <strong>' + payload.quote.labels.retention + '</strong>, SLA de restore <strong>' + payload.quote.sla + '</strong>, ' + payload.quote.labels.compliance + ' e topologia em <strong>' + payload.quote.labels.redundancy + '</strong>.</p>',
        '<h6>2. Condições comerciais</h6>',
        '<p>Para esta simulação, o valor mensal equivalente é estimado em <strong>' + storageQuoteFormatter.format(payload.monthlyService) + '</strong>, com setup inicial de <strong>' + storageQuoteFormatter.format(payload.setupFee) + '</strong> e valor contratual projetado de <strong>' + storageQuoteFormatter.format(payload.contractValue) + '</strong> ao longo de <strong>' + termLabel + '</strong>, sob regime de <strong>' + billingLabel + '</strong>.</p>',
        '<ul>',
        '<li>Benchmark de mercado equivalente: ' + storageQuoteFormatter.format(payload.quote.monthlyMarket) + ' por mês.</li>',
        '<li>Economia potencial frente à referência: ' + storageQuoteFormatter.format(payload.quote.monthlySavings) + ' por mês.</li>',
        '<li>Janela inicial proposta para ativação ou sizing: ' + startDate + '.</li>',
        '</ul>',
        '<h6>3. Ativação e obrigações</h6>',
        '<p>A RPA4ALL executará o desenho de ativação, onboarding e políticas operacionais conforme os dados acima. O cliente se compromete a fornecer acessos, inventário, janelas de mudança, contatos de aprovação e premissas de compliance necessárias para execução do serviço.</p>',
        '<h6>4. Saída honrosa e rescisão planejada</h6>',
        '<p>As partes poderão encerrar a contratação por meio de <strong>saída honrosa</strong>, com aviso prévio mínimo de <strong>' + payload.noticeDays + ' dias</strong>, transição assistida, quitação dos valores vencidos e manutenção das obrigações de confidencialidade durante o handoff.</p>',
        '<h6>5. Quebra contratual</h6>',
        '<p>Configura quebra contratual, entre outros, inadimplência superior a 30 dias, uso indevido da capacidade provisionada, violação de confidencialidade, omissão de informações críticas que inviabilizem a operação ou descumprimento reiterado das obrigações técnicas assumidas.</p>',
        '<p>Nessas hipóteses, poderá ser aplicada penalidade comercial inicial estimada em <strong>' + storageQuoteFormatter.format(payload.breachPenalty) + '</strong>, sem prejuízo da cobrança de perdas adicionais comprovadas.</p>',
        (notes
          ? '<h6>6. Observações da solicitação</h6><p>' + notes + '</p>'
          : ''),
        '<h6>7. Natureza do documento</h6>',
        '<p>Esta minuta tem finalidade pré-contratual e serve como base para revisão comercial, jurídica e fiscal antes da assinatura definitiva.</p>'
      ].join('');
    }

    function calculate() {
      const state = buildRequestState();
      latestRequestState = state;

      outputs.offerMonthly.textContent = storageQuoteFormatter.format(state.monthlyService);
      outputs.monthlyRecurring.textContent = storageQuoteFormatter.format(state.monthlyService) + '/mês';
      outputs.billingLabel.textContent = state.billingLabel;
      outputs.setupFee.textContent = storageQuoteFormatter.format(state.setupFee);
      outputs.startLabel.textContent = 'início pretendido em ' + state.startDate;
      outputs.contractValue.textContent = storageQuoteFormatter.format(state.contractValue);
      outputs.contractTermLabel.textContent = 'vigência de ' + state.termLabel;
      outputs.breachPenalty.textContent = storageQuoteFormatter.format(state.breachPenalty);
      outputs.exitTerms.textContent = 'saída honrosa com aviso de ' + state.noticeDays + ' dias';
      outputs.temperatureLabel.textContent = state.quote.tier.label;
      outputs.breakdown.innerHTML = [
        '<li>Empresa solicitante: <strong>' + escapeHtml(state.company) + '</strong> para o projeto <strong>' + escapeHtml(state.project) + '</strong>.</li>',
        '<li>Oferta equivalente: <strong>' + storageQuoteFormatter.format(state.monthlyService) + '/mês</strong> em ' + state.quote.tier.label + ' com ' + state.quote.labels.redundancy + '.</li>',
        '<li>Setup inicial estimado: <strong>' + storageQuoteFormatter.format(state.setupFee) + '</strong> com início pretendido em <strong>' + state.startDate + '</strong>.</li>',
        '<li>Condição comercial: <strong>' + state.billingLabel + '</strong> por <strong>' + state.termLabel + '</strong>.</li>',
        '<li>Saída honrosa: aviso prévio de <strong>' + state.noticeDays + ' dias</strong>; quebra contratual base em <strong>' + storageQuoteFormatter.format(state.breachPenalty) + '</strong>.</li>'
      ].join('');
      outputs.contractMetaCustomer.textContent = 'Cliente: ' + state.company;
      outputs.contractMetaProject.textContent = 'Projeto: ' + state.project;
      outputs.contractMetaStart.textContent = 'Início: ' + state.startDate;
      outputs.contractPreview.innerHTML = buildRequestContract({
        company: state.company,
        legalName: state.legalName,
        contact: state.contact,
        role: state.role,
        email: state.email,
        phone: state.phone,
        project: state.project,
        city: state.city,
        state: state.state,
        notes: state.notes,
        startDate: state.startDate,
        termLabel: state.termLabel,
        billingLabel: state.billingLabel,
        quote: state.quote,
        monthlyService: state.monthlyService,
        setupFee: state.setupFee,
        contractValue: state.contractValue,
        noticeDays: state.noticeDays,
        breachPenalty: state.breachPenalty
      });

      safeJsonSet(storageRequestStorageKey, {
        company: fields.company.value,
        legalName: fields.legalName.value,
        contact: fields.contact.value,
        role: fields.role.value,
        email: fields.email.value,
        phone: fields.phone.value,
        project: fields.project.value,
        temperature: fields.temperature.value,
        volume: fields.volume.value,
        ingress: fields.ingress.value,
        retention: fields.retention.value,
        retrieval: fields.retrieval.value,
        sla: fields.sla.value,
        compliance: fields.compliance.value,
        redundancy: fields.redundancy.value,
        billing: fields.billing.value,
        term: fields.term.value,
        startDate: fields.startDate.value,
        city: fields.city.value,
        state: fields.state.value,
        notes: fields.notes.value
      });
    }

    function hydrateFromSnapshot(snapshot) {
      if (!snapshot) return;
      Object.entries(snapshot).forEach(([key, value]) => {
        const field = fields[key];
        if (field && value != null) {
          field.value = value;
        }
      });
    }

    function applyModeContent() {
      const content = modeContent[mode] || modeContent.sizing;
      outputs.modeEyebrow.textContent = content.eyebrow;
      outputs.pageTitle.textContent = content.title;
      outputs.pageLead.textContent = content.lead;
      outputs.summaryTitle.textContent = content.summaryTitle;
      outputs.summaryNote.textContent = content.summaryNote;
      outputs.resultsKicker.textContent = content.resultsKicker;
      outputs.contractTitle.textContent = content.contractTitle;
      if (provisionButton) {
        provisionButton.textContent = content.actionLabel;
      }
      if (provisionHint) {
        provisionHint.textContent = content.actionHint;
      }
      document.title = mode === 'space'
        ? 'RPA4ALL — Solicitação de Espaço'
        : 'RPA4ALL — Solicitação de Sizing';
    }

    const savedRequest = safeJsonGet(storageRequestStorageKey, null);
    const savedStorageQuote = safeJsonGet(storageQuoteStorageKey, null);
    applyModeContent();
    hydrateFromSnapshot(savedRequest);
    if (!fields.startDate.value) {
      const initialDate = new Date();
      initialDate.setDate(initialDate.getDate() + 14);
      fields.startDate.value = initialDate.toISOString().slice(0, 10);
    }
    if (!savedRequest && savedStorageQuote) {
      ['temperature', 'volume', 'ingress', 'retention', 'retrieval', 'sla', 'compliance', 'redundancy']
        .forEach(key => {
          if (savedStorageQuote[key] != null) {
            fields[key].value = savedStorageQuote[key];
          }
        });
    }

    if (syncButton) {
      syncButton.addEventListener('click', () => {
        const snapshot = safeJsonGet(storageQuoteStorageKey, null);
        if (!snapshot) return;
        ['temperature', 'volume', 'ingress', 'retention', 'retrieval', 'sla', 'compliance', 'redundancy']
          .forEach(key => {
            if (snapshot[key] != null) {
              fields[key].value = snapshot[key];
            }
          });
        calculate();
      });
    }

    if (copyButton) {
      copyButton.addEventListener('click', async () => {
        if (!outputs.contractPreview) return;
        const originalText = copyButton.textContent;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(outputs.contractPreview.innerText.trim());
            copyButton.textContent = 'Contrato copiado';
          } else {
            copyButton.textContent = 'Copie manualmente';
          }
        } catch (error) {
          copyButton.textContent = 'Copie manualmente';
        }

        window.setTimeout(() => {
          copyButton.textContent = originalText;
        }, 1800);
      });
    }

    if (provisionButton) {
      provisionButton.addEventListener('click', async () => {
        const actionLabel = (modeContent[mode] || modeContent.sizing).actionLabel;
        const state = latestRequestState || buildRequestState();
        const validationError = validateProvisionRequest(state);
        if (validationError) {
          setProvisionStatus(validationError, 'error');
          return;
        }

        provisionButton.disabled = true;
        provisionButton.textContent = 'Gerando acesso...';
        setProvisionStatus('Gerando login no portal e preparando o envio das credenciais por email.', 'pending');

        try {
          const result = await postProvisionRequest(buildProvisionPayload(state));
          const successMessage = result && result.message
            ? result.message + '. Confira também o spam se o email não chegar em poucos minutos.'
            : 'Acesso gerado com sucesso. As credenciais foram enviadas por email.';
          setProvisionStatus(successMessage, 'success');
        } catch (error) {
          const message = error && error.message
            ? error.message
            : 'Não foi possível provisionar o acesso agora. Tente novamente em alguns minutos.';
          setProvisionStatus(message, 'error');
        } finally {
          provisionButton.disabled = false;
          provisionButton.textContent = actionLabel;
        }
      });
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
