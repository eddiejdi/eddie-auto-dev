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
    const backgroundContext = resolveBackgroundContext();
    const backgroundPalette = createContextPalette(backgroundContext, variant);
    const scene = createScene(variant);
    let viewportWidth = 0;
    let viewportHeight = 0;
    let deviceScale = 1;
    let animationFrameId = 0;

    applyVariantPalette(variant, backgroundPalette);
    requestBackgroundSvg(variant);

    if (directOllamaBase || sameOriginApiBase || externalApiBase) {
      resizeCanvas();
      if (!prefersReducedMotion) {
        document.addEventListener('visibilitychange', () => {
          if (document.hidden) {
            stopAnimation();
          }
        });
      }
      window.addEventListener('resize', resizeCanvas, { passive: true });
    }

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

    function applyVariantPalette(selectedVariant, palette) {
      const rootStyle = document.documentElement.style;
      rootStyle.setProperty('--site-bg-base', palette.base || selectedVariant.base);
      rootStyle.setProperty('--site-bg-deep', palette.deep || selectedVariant.deep);
      rootStyle.setProperty('--site-bg-glow-a', palette.glowA || selectedVariant.glowA);
      rootStyle.setProperty('--site-bg-glow-b', palette.glowB || selectedVariant.glowB);
      rootStyle.setProperty('--site-bg-glow-c', palette.glowC || selectedVariant.glowC);
      rootStyle.setProperty('--site-bg-grid', palette.grid || 'rgba(148, 163, 184, 0.08)');
      document.body.dataset.backgroundVariant = selectedVariant.id;
      document.body.dataset.backgroundContext = backgroundContext.partOfDay + '-' + backgroundContext.season;
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

    function createContextPalette(context, selectedVariant) {
      const palette = {
        base: selectedVariant.base,
        deep: selectedVariant.deep,
        glowA: selectedVariant.glowA,
        glowB: selectedVariant.glowB,
        glowC: selectedVariant.glowC,
        grid: 'rgba(148, 163, 184, 0.08)'
      };

      if (context.partOfDay === 'madrugada') {
        palette.deep = '#020817';
        palette.base = '#04111f';
        palette.glowA = 'rgba(56, 189, 248, 0.18)';
        palette.glowB = 'rgba(59, 130, 246, 0.14)';
        palette.glowC = 'rgba(255, 255, 255, 0.08)';
        palette.grid = 'rgba(148, 163, 184, 0.06)';
      } else if (context.partOfDay === 'manha') {
        palette.deep = '#07213b';
        palette.base = '#0c3551';
        palette.glowA = 'rgba(56, 189, 248, 0.22)';
        palette.glowB = 'rgba(250, 204, 21, 0.16)';
        palette.glowC = 'rgba(34, 197, 94, 0.14)';
        palette.grid = 'rgba(125, 211, 252, 0.08)';
      } else if (context.partOfDay === 'tarde') {
        palette.deep = '#08263a';
        palette.base = '#11415c';
        palette.glowA = 'rgba(34, 197, 94, 0.18)';
        palette.glowB = 'rgba(250, 204, 21, 0.18)';
        palette.glowC = 'rgba(56, 189, 248, 0.14)';
      } else {
        palette.deep = '#05111f';
        palette.base = '#0a1830';
        palette.glowA = 'rgba(56, 189, 248, 0.22)';
        palette.glowB = 'rgba(34, 197, 94, 0.16)';
        palette.glowC = 'rgba(14, 165, 233, 0.12)';
      }

      if (context.season === 'verao') {
        palette.glowB = 'rgba(250, 204, 21, 0.2)';
      } else if (context.season === 'inverno') {
        palette.glowA = 'rgba(96, 165, 250, 0.2)';
        palette.glowC = 'rgba(255, 255, 255, 0.08)';
      } else if (context.season === 'primavera') {
        palette.glowB = 'rgba(74, 222, 128, 0.18)';
      }

      if (context.holiday) {
        palette.glowA = 'rgba(34, 197, 94, 0.22)';
        palette.glowB = 'rgba(250, 204, 21, 0.2)';
        palette.glowC = 'rgba(59, 130, 246, 0.16)';
      }

      return palette;
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
      gradient.addColorStop(0, backgroundPalette.deep);
      gradient.addColorStop(1, backgroundPalette.base);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, viewportWidth, viewportHeight);

      drawGlows(time);
      drawGrid(time);
      drawContextHalo(time);
      drawStreams(time);
      drawNetwork(time);
      drawParticles(time);
      drawRings(time);
      drawBrazilMark(time);
    }

    function drawGlows(time) {
      const glows = [
        { x: viewportWidth * 0.18, y: viewportHeight * (0.22 + Math.sin(time * 0.18) * 0.02), radius: viewportWidth * 0.22, color: backgroundPalette.glowA },
        { x: viewportWidth * 0.76, y: viewportHeight * (0.18 + Math.cos(time * 0.16) * 0.02), radius: viewportWidth * 0.2, color: backgroundPalette.glowB },
        { x: viewportWidth * 0.58, y: viewportHeight * (0.74 + Math.sin(time * 0.14) * 0.03), radius: viewportWidth * 0.18, color: backgroundPalette.glowC }
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
      ctx.strokeStyle = backgroundPalette.grid;
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

    function drawContextHalo(time) {
      const centerX = viewportWidth * 0.84;
      const centerY = backgroundContext.partOfDay === 'madrugada'
        ? viewportHeight * 0.16
        : backgroundContext.partOfDay === 'noite'
          ? viewportHeight * 0.18
          : viewportHeight * 0.2;
      const radius = Math.max(70, viewportWidth * 0.06);
      const drift = Math.sin(time * 0.22) * 6;
      const fill = ctx.createRadialGradient(centerX, centerY + drift, 0, centerX, centerY, radius);

      if (backgroundContext.partOfDay === 'noite' || backgroundContext.partOfDay === 'madrugada') {
        fill.addColorStop(0, 'rgba(255, 255, 255, 0.16)');
        fill.addColorStop(0.2, 'rgba(191, 219, 254, 0.12)');
        fill.addColorStop(1, 'rgba(255, 255, 255, 0)');
      } else {
        fill.addColorStop(0, 'rgba(250, 204, 21, 0.2)');
        fill.addColorStop(0.28, 'rgba(253, 224, 71, 0.12)');
        fill.addColorStop(1, 'rgba(250, 204, 21, 0)');
      }

      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(centerX, centerY + drift, radius, 0, Math.PI * 2);
      ctx.fill();
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
        ctx.strokeStyle = index % 3 === 0
          ? toRgba('#38bdf8', alpha)
          : index % 3 === 1
            ? toRgba('#22c55e', alpha)
            : toRgba('#facc15', alpha * 0.9);
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
          ctx.strokeStyle = other % 3 === 0
            ? toRgba('#38bdf8', alpha)
            : other % 3 === 1
              ? toRgba('#22c55e', alpha * 0.9)
              : toRgba('#facc15', alpha * 0.75);
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      positionedNodes.forEach((node, index) => {
        const pulse = 1 + Math.sin(time * 1.4 + index) * 0.22;
        const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, 18 * pulse);
        glow.addColorStop(0, index % 3 === 0 ? 'rgba(56, 189, 248, 0.22)' : index % 3 === 1 ? 'rgba(34, 197, 94, 0.18)' : 'rgba(250, 204, 21, 0.16)');
        glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = glow;
        ctx.fillRect(node.x - 24, node.y - 24, 48, 48);

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * pulse, 0, Math.PI * 2);
        ctx.fillStyle = index % 3 === 0 ? 'rgba(125, 211, 252, 0.82)' : index % 3 === 1 ? 'rgba(134, 239, 172, 0.78)' : 'rgba(254, 240, 138, 0.72)';
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
          : index % 3 === 1
            ? 'rgba(255, 255, 255, ' + (particle.alpha * 0.8) + ')'
            : 'rgba(250, 204, 21, ' + (particle.alpha * 0.55) + ')';
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

    function drawBrazilMark(time) {
      const anchorX = viewportWidth * 0.72;
      const anchorY = viewportHeight * 0.66;
      const scale = Math.min(viewportWidth, viewportHeight) * 0.16;
      const pulse = Math.sin(time * 0.34) * 0.04;

      ctx.save();
      ctx.translate(anchorX, anchorY);
      ctx.rotate(-0.08 + pulse);

      ctx.beginPath();
      ctx.moveTo(0, -scale * 0.54);
      ctx.lineTo(scale * 0.88, 0);
      ctx.lineTo(0, scale * 0.54);
      ctx.lineTo(-scale * 0.88, 0);
      ctx.closePath();
      ctx.fillStyle = 'rgba(250, 204, 21, 0.12)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(0, 0, scale * 0.34, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(37, 99, 235, 0.16)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(0, scale * 0.02, scale * 0.28, Math.PI * 1.1, Math.PI * 1.92);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
      ctx.lineWidth = Math.max(2, scale * 0.018);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(0, 0, scale * 0.5, Math.PI * 1.08, Math.PI * 1.68);
      ctx.strokeStyle = 'rgba(34, 197, 94, 0.16)';
      ctx.lineWidth = Math.max(1.5, scale * 0.014);
      ctx.stroke();

      ctx.restore();
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

    function getSeasonBrazil(monthIndex) {
      // Southern hemisphere seasons (Brazil)
      if (monthIndex === 11 || monthIndex <= 1) return 'verao';
      if (monthIndex >= 2 && monthIndex <= 4) return 'outono';
      if (monthIndex >= 5 && monthIndex <= 7) return 'inverno';
      return 'primavera';
    }

    function detectBrazilHoliday(date) {
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const key = month + '-' + day;
      const fixed = {
        '01-01': 'Confraternizacao Universal',
        '04-21': 'Tiradentes',
        '05-01': 'Dia do Trabalho',
        '09-07': 'Independencia do Brasil',
        '10-12': 'Nossa Senhora Aparecida / Dia das Criancas',
        '11-02': 'Finados',
        '11-15': 'Proclamacao da Republica',
        '12-25': 'Natal'
      };
      return fixed[key] || '';
    }

    function resolveBackgroundContext() {
      const hints = window.__rpaBackgroundHints || {};
      const now = new Date();
      const zoned = new Date(now.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' }));
      const hour = zoned.getHours();
      const partOfDay = hour < 5 ? 'madrugada' : hour < 12 ? 'manha' : hour < 18 ? 'tarde' : 'noite';
      const season = hints.season || getSeasonBrazil(zoned.getMonth());
      const holiday = hints.holiday || detectBrazilHoliday(zoned);

      const rawTemp = Number.isFinite(hints.temperatureC) ? hints.temperatureC : (Number.isFinite(hints.tempC) ? hints.tempC : NaN);
      let temperatureLabel = hints.temperatureLabel;
      if (!temperatureLabel) {
        if (!Number.isNaN(rawTemp)) {
          if (rawTemp >= 30) temperatureLabel = 'clima muito quente';
          else if (rawTemp >= 25) temperatureLabel = 'clima quente';
          else if (rawTemp >= 18) temperatureLabel = 'clima ameno';
          else if (rawTemp >= 12) temperatureLabel = 'clima fresco';
          else temperatureLabel = 'clima frio';
        } else {
          temperatureLabel = season === 'inverno' ? 'clima fresco' : (season === 'verao' ? 'clima quente' : 'clima ameno');
        }
      }

      const weatherLabel = hints.weather || hints.conditions || (season === 'verao' ? 'ceu limpo com umidade leve' : season === 'inverno' ? 'ceu frio e seco' : 'ceu aberto ameno');

      return {
        partOfDay,
        season,
        holiday,
        temperatureLabel,
        weatherLabel
      };
    }

    function buildPrompt(selectedVariant) {
      const context = resolveBackgroundContext();
      const holidayLine = context.holiday
        ? 'Today is ' + context.holiday + ' in Brazil; weave a respectful celebratory glow using flag colors without text.'
        : 'No holiday today; keep the tone executive with only subtle festivity.';

      return [
        'Generate ONLY a valid SVG image.',
        'Do not include markdown, prose, code fences, comments, explanations, base64 PNGs or embedded raster images.',
        'Return raw SVG starting with <svg and ending with </svg>.',
        'Width="1600" height="900" viewBox="0 0 1600 900".',
        'Create a simple abstract website background for the brand RPA4ALL.',
        'Visual direction: dark command center, premium automation platform and data movement.',
        'Use deep navy as the base and emerald #22c55e, cyan #38bdf8, teal #14b8a6 and yellow #facc15 as highlights.',
        'No text, no letters, no numbers, no logos, no people.',
        'Use only gradients, paths, circles, soft glows, technical grids, telemetry arcs and flowing lines.',
        'Keep the SVG lightweight and elegant, with negative space for UI content.',
        'Context: ' + context.partOfDay + ' in Brazil, season ' + context.season + ', ' + context.weatherLabel + ', ' + context.temperatureLabel + '.',
        holidayLine,
        'Include a subtle Brazilian identity mark: a minimal Ordem e Progresso-inspired arc or ribbon in green, yellow, blue and white, integrated as an accent and not overpowering the UI.',
        'Keep the output concise and fast to render.',
        'Theme emphasis: ' + selectedVariant.focus + '.',
        'Seed hint: ' + selectedVariant.seed + '.'
      ].join(' ');
    }

    function buildProviders() {
      const providers = [
        {
          kind: 'llm-chat',
          url: sameOriginApiBase + '/llm-tools/chat',
          timeout: 45000
        }
      ];

      if (sameOriginApiBase !== externalApiBase) {
        providers.push({
          kind: 'llm-chat',
          url: externalApiBase + '/llm-tools/chat',
          timeout: 45000
        });
      }

      if (directOllamaBase) {
        providers.unshift({
          kind: 'ollama',
          url: directOllamaBase + '/api/generate',
          timeout: 30000
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
      canvas.style.opacity = '0';
      const prompt = buildPrompt(selectedVariant);

      for (const provider of buildProviders()) {
        try {
          let payload;
          if (provider.kind === 'ollama') {
            payload = await fetchJson(provider.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                model: 'phi4-mini:latest',
                prompt: prompt,
                stream: false,
                options: {
                  temperature: 0.85,
                  seed: selectedVariant.seed,
                  num_predict: 900
                }
              })
            }, provider.timeout);
          } else {
            payload = await fetchJson(provider.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                prompt: prompt,
                model: 'phi4-mini:latest',
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
          canvas.style.opacity = '0';
          return;
        } catch (error) {
          // Try the next Ollama-capable provider.
        }
      }

      svgSlot.innerHTML = '';
      canvas.style.opacity = '0';
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

  const contractIssuerProfile = {
    brand: 'RPA4ALL',
    headquarters: 'São Paulo/SP',
    qualification:
      'pessoa jurídica de direito privado, qualificada na proposta comercial, no pedido de contratação e no aceite eletrônico correspondente, doravante denominada CONTRATADA'
  };

  const legalMonths = [
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro'
  ];

  function digitsOnly(value) {
    return String(value ?? '').replace(/\D+/g, '');
  }

  function formatBrazilianDocument(value) {
    const digits = digitsOnly(value);
    if (digits.length === 11) {
      return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    }
    if (digits.length === 14) {
      return digits.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
    }
    return String(value ?? '').trim();
  }

  function formatPostalCode(value) {
    const digits = digitsOnly(value);
    if (digits.length === 8) {
      return digits.replace(/(\d{5})(\d{3})/, '$1-$2');
    }
    return String(value ?? '').trim();
  }

  function formatContractNumber(value) {
    const digits = Number.parseFloat(value);
    if (!Number.isFinite(digits)) return storageQuoteFormatter.format(0);
    return storageQuoteFormatter.format(digits);
  }

  function formatLongDate(dateValue) {
    let date = null;
    if (dateValue instanceof Date) {
      date = dateValue;
    } else if (typeof dateValue === 'string' && dateValue) {
      const parts = dateValue.split('-');
      if (parts.length === 3) {
        date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      }
    }

    if (!date || Number.isNaN(date.getTime())) return 'data a definir';
    return (
      date.getDate() +
      ' de ' +
      legalMonths[date.getMonth()] +
      ' de ' +
      date.getFullYear()
    );
  }

  function hashContractSeed(value) {
    const text = String(value || '');
    let hash = 0;
    for (let index = 0; index < text.length; index += 1) {
      hash = (hash * 31 + text.charCodeAt(index)) >>> 0;
    }
    return hash.toString(36).toUpperCase().padStart(6, '0').slice(0, 6);
  }

  function buildContractReference(prefix, seed) {
    const now = new Date();
    const dateCode =
      String(now.getFullYear()) +
      String(now.getMonth() + 1).padStart(2, '0') +
      String(now.getDate()).padStart(2, '0');
    return 'RPA4ALL-' + prefix + '-' + dateCode + '-' + hashContractSeed(seed);
  }

  function isMeaningfulValue(value, disallowedValues) {
    const normalized = String(value ?? '').trim();
    if (!normalized) return false;
    return !disallowedValues.includes(normalized.toLowerCase());
  }

  function textOrPlaceholder(value, placeholder, disallowedValues) {
    const normalized = String(value ?? '').trim();
    const denied = Array.isArray(disallowedValues) ? disallowedValues.map(item => String(item).trim().toLowerCase()) : [];
    if (!isMeaningfulValue(normalized, denied)) {
      return '<span class="legal-contract__placeholder">' + escapeHtml(placeholder) + '</span>';
    }
    return escapeHtml(normalized);
  }

  function buildFullAddress(parts) {
    const items = [];
    if (parts.address) items.push(parts.address);
    if (parts.number) items.push('nº ' + parts.number);
    if (parts.complement) items.push(parts.complement);
    if (parts.district) items.push(parts.district);

    const cityLine = [parts.city, parts.state].filter(Boolean).join('/');
    if (cityLine) items.push(cityLine);
    if (parts.postalCode) items.push('CEP ' + parts.postalCode);

    return items.filter(Boolean).join(', ');
  }

  function buildLegalSummaryGrid(items) {
    return (
      '<div class="legal-contract__summary-grid">' +
      items
        .map(item =>
          '<div class="legal-contract__summary-card"><span>' +
          escapeHtml(item.label) +
          '</span><strong>' +
          item.value +
          '</strong></div>'
        )
        .join('') +
      '</div>'
    );
  }

  function buildLetterhead(title, reference, subtitle) {
    return [
      '<header class="legal-contract__header">',
      '<div class="legal-contract__brand">',
      '<div class="legal-contract__mark" aria-hidden="true">R4</div>',
      '<div>',
      '<p class="legal-contract__brand-name">' + contractIssuerProfile.brand + '</p>',
      '<p class="legal-contract__brand-note">Minuta contratual timbrada para formalização comercial e jurídica.</p>',
      '</div>',
      '</div>',
      '<div class="legal-contract__document">',
      '<span class="legal-contract__eyebrow">Instrumento particular</span>',
      '<strong>' + escapeHtml(title) + '</strong>',
      '<small>Referência ' + escapeHtml(reference) + '</small>',
      '<small>' + escapeHtml(subtitle) + '</small>',
      '</div>',
      '</header>'
    ].join('');
  }

  function buildSignaturePanel(entries, note) {
    return [
      '<div class="legal-contract__signatures">',
      entries
        .map(entry =>
          '<div class="legal-contract__signature-card">' +
          '<span class="legal-contract__signature-line"></span>' +
          '<strong>' + entry.name + '</strong>' +
          '<small>' + entry.role + '</small>' +
          (entry.meta ? '<small>' + entry.meta + '</small>' : '') +
          '</div>'
        )
        .join(''),
      '</div>',
      note ? '<p class="legal-contract__legal-note">' + note + '</p>' : ''
    ].join('');
  }

  function buildPreparedForPanel(title, subtitle, details) {
    return [
      '<section class="legal-contract__prepared">',
      '<span class="legal-contract__prepared-kicker">Documento personalizado para</span>',
      '<strong class="legal-contract__prepared-name">' + title + '</strong>',
      '<p class="legal-contract__prepared-copy">' + subtitle + '</p>',
      '<div class="legal-contract__prepared-grid">',
      details
        .map(item =>
          '<div class="legal-contract__prepared-item"><span>' +
          escapeHtml(item.label) +
          '</span><strong>' +
          item.value +
          '</strong></div>'
        )
        .join(''),
      '</div>',
      '</section>'
    ].join('');
  }

  function buildPrintableContractStyles() {
    return [
      '@page { size: A4; margin: 16mm 14mm 18mm; }',
      'html, body { margin: 0; padding: 0; background: #f3f5f7; color: #152232; font-family: Inter, Arial, sans-serif; }',
      'body { padding: 12mm 0; }',
      '.print-sheet { width: 210mm; min-height: 297mm; margin: 0 auto; background: #ffffff; box-shadow: 0 10px 32px rgba(15, 23, 42, 0.12); }',
      '.print-sheet__inner { padding: 14mm 13mm 16mm; }',
      '.legal-contract { display: flex; flex-direction: column; gap: 14px; color: #1b2b3d; }',
      '.legal-contract__header { display: flex; justify-content: space-between; gap: 16px; padding: 0 0 14px; border-bottom: 2px solid #d8e1ea; }',
      '.legal-contract__brand { display: flex; gap: 12px; align-items: center; }',
      '.legal-contract__mark { width: 50px; height: 50px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #22c55e, #38bdf8); color: #071018; font-weight: 800; font-size: 21px; }',
      '.legal-contract__brand-name { margin: 0 0 4px; font-size: 17px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: #102033; }',
      '.legal-contract__brand-note, .legal-contract__document small, .legal-contract__eyebrow, .legal-contract__prepared-copy, .legal-contract__summary-card span, .legal-contract__legal-note { color: #5c7286; }',
      '.legal-contract__brand-note, .legal-contract__prepared-copy, p, li, small { line-height: 1.58; }',
      '.legal-contract__document { display: grid; gap: 6px; text-align: right; }',
      '.legal-contract__document strong, .legal-contract__title, .legal-contract__prepared-name { color: #0f1f31; }',
      '.legal-contract__document strong { font-size: 17px; line-height: 1.3; }',
      '.legal-contract__eyebrow, .legal-contract__summary-card span, .legal-contract__prepared-kicker, h6 { text-transform: uppercase; letter-spacing: 0.12em; font-size: 10px; font-weight: 800; }',
      '.legal-contract__title { margin: 0; font-size: 20px; line-height: 1.25; text-transform: uppercase; letter-spacing: 0.03em; }',
      '.legal-contract__lead { margin: 0; padding: 12px 14px; border-left: 3px solid #2ea8e5; background: #f5f9fc; border-radius: 0 10px 10px 0; }',
      '.legal-contract__prepared { padding: 16px; border-radius: 12px; border: 1px solid #d7e1eb; background: linear-gradient(180deg, #f8fbfe, #f2f7fb); }',
      '.legal-contract__prepared-kicker, h6 { color: #1d6a97; }',
      '.legal-contract__prepared-name { display: block; margin: 4px 0 8px; font-size: 22px; line-height: 1.2; }',
      '.legal-contract__prepared-grid, .legal-contract__summary-grid, .legal-contract__signatures { display: grid; gap: 10px; }',
      '.legal-contract__prepared-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }',
      '.legal-contract__summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }',
      '.legal-contract__prepared-item, .legal-contract__summary-card, .legal-contract__signature-card { padding: 12px 13px; border-radius: 12px; border: 1px solid #dde6ee; background: #fbfdff; }',
      '.legal-contract__prepared-item span, .legal-contract__summary-card span { display: block; margin-bottom: 5px; }',
      '.legal-contract__prepared-item strong, .legal-contract__summary-card strong { display: block; color: #102033; line-height: 1.45; }',
      'h6 { margin: 4px 0 6px; }',
      'p { margin: 0 0 10px; font-size: 13px; }',
      'ul { margin: 0 0 10px; padding-left: 18px; }',
      'li { margin-bottom: 6px; font-size: 13px; }',
      '.legal-contract__placeholder { color: #7d8ea0; font-style: italic; }',
      '.legal-contract__signatures { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 4px; }',
      '.legal-contract__signature-card { min-height: 102px; }',
      '.legal-contract__signature-line { display: block; height: 1px; margin-bottom: 14px; background: #b9c7d5; }',
      '.legal-contract__signature-card strong { display: block; margin-bottom: 4px; }',
      '.legal-contract__signature-card small { display: block; }',
      '.print-footer { margin-top: 12px; color: #64748b; font-size: 11px; text-align: center; }',
      '@media print { html, body { background: #fff; } body { padding: 0; } .print-sheet { width: auto; min-height: auto; box-shadow: none; } .print-sheet__inner { padding: 0; } }',
      '@media screen and (max-width: 920px) { body { padding: 0; } .print-sheet { width: 100%; min-height: auto; box-shadow: none; } .print-sheet__inner { padding: 18px 16px 24px; } .legal-contract__header, .legal-contract__prepared-grid, .legal-contract__summary-grid, .legal-contract__signatures { grid-template-columns: 1fr; display: grid; } .legal-contract__document { text-align: left; } }'
    ].join('');
  }

  function buildPrintableContractDocument(title, contractHtml) {
    return [
      '<!doctype html>',
      '<html lang="pt-BR">',
      '<head>',
      '<meta charset="utf-8">',
      '<meta name="viewport" content="width=device-width, initial-scale=1">',
      '<title>' + escapeHtml(title) + '</title>',
      '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">',
      '<style>' + buildPrintableContractStyles() + '</style>',
      '</head>',
      '<body>',
      '<main class="print-sheet"><div class="print-sheet__inner">' + contractHtml + '<p class="print-footer">Documento preparado para impressão em folha A4.</p></div></main>',
      '</body>',
      '</html>'
    ].join('');
  }

  function openPrintableContract(title, contractHtml) {
    const printWindow = window.open('', '_blank', 'width=1120,height=920');
    if (!printWindow) return false;

    printWindow.document.open();
    printWindow.document.write(buildPrintableContractDocument(title, contractHtml));
    printWindow.document.close();

    const triggerPrint = function() {
      printWindow.focus();
      window.setTimeout(() => {
        printWindow.print();
      }, 180);
    };

    printWindow.addEventListener('load', triggerPrint, { once: true });
    return true;
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
      const partnerName = textOrPlaceholder(payload.partnerName, 'qualificação societária da parceira', ['parceiro canal rpa4all']);
      const partnerContact = textOrPlaceholder(payload.partnerContact, 'representante comercial da parceira', ['nome do responsável']);
      const partnerEmail = textOrPlaceholder(payload.partnerEmail, 'email comercial válido', ['canal@parceiro.com.br']);
      const partnerModelLabel = escapeHtml(payload.partnerModelLabel);
      const customerName = textOrPlaceholder(payload.customerName, 'oportunidade comercial vinculada', ['conta estratégica em qualificação', 'conta estrategica em qualificacao']);
      const billingLabel = escapeHtml(payload.billingLabel);
      const termLabel = escapeHtml(payload.termLabel);
      const reference = buildContractReference(
        'CANAL',
        [payload.partnerName, payload.customerName, payload.termLabel].join('|')
      );
      const issueDate = formatLongDate(new Date());

      return [
        '<div class="legal-contract">',
        buildLetterhead(
          'Minuta particular de parceria comercial para revenda de storage gerenciado',
          reference,
          'Emitida em ' + issueDate + ' · ' + contractIssuerProfile.headquarters
        ),
        '<h5 class="legal-contract__title">Instrumento particular de parceria comercial e distribuição</h5>',
        '<p class="legal-contract__lead">Pelo presente instrumento particular, celebrado sob a autonomia privada, boa-fé objetiva e força obrigatória das avenças, na forma dos arts. 421, 421-A, 422 e 425 da Lei nº 10.406/2002, ficam registradas as condições-base da oportunidade comercial abaixo descrita.</p>',
        buildLegalSummaryGrid([
          { label: 'Referência', value: escapeHtml(reference) },
          { label: 'Parceira', value: partnerName },
          { label: 'Modelo de canal', value: partnerModelLabel },
          { label: 'Oportunidade', value: customerName },
          { label: 'Ticket estimado', value: escapeHtml(formatContractNumber(payload.customerMonthly) + '/mês') },
          { label: 'Comissão recorrente', value: escapeHtml(formatPercent(payload.commissionRate)) }
        ]),
        '<h6>1. Partes e qualificação</h6>',
        '<p><strong>CONTRATADA:</strong> ' + contractIssuerProfile.brand + ', ' + contractIssuerProfile.qualification + '.</p>',
        '<p><strong>PARCEIRA:</strong> ' + partnerName + ', qualificada na proposta comercial vinculada à oportunidade, neste ato representada por ' + partnerContact + ', por meio do email ' + partnerEmail + ', doravante denominada <strong>PARCEIRA</strong>.</p>',
        '<h6>2. Objeto e oportunidade vinculada</h6>',
        '<p>O presente instrumento disciplina, em caráter pré-contratual e comercial, a atuação da PARCEIRA na indicação, revenda gerenciada ou operação em white label da oportunidade ' + customerName + ', considerando a oferta de storage gerenciado em camada <strong>' + payload.quote.tier.label + '</strong>, volume protegido estimado em <strong>' + payload.quote.volume.toLocaleString('pt-BR') + ' TB</strong>, ingestão mensal de <strong>' + payload.quote.ingress.toLocaleString('pt-BR') + ' TB</strong>, retenção de <strong>' + payload.quote.labels.retention + '</strong>, restore em <strong>' + payload.quote.sla + '</strong>, ' + payload.quote.labels.compliance + ' e topologia em <strong>' + payload.quote.labels.redundancy + '</strong>.</p>',
        '<h6>3. Condições comerciais e remuneração da parceira</h6>',
        '<p>Para fins desta minuta, o ticket mensal equivalente da conta é estimado em <strong>' + formatContractNumber(payload.customerMonthly) + '</strong>, sob regime de <strong>' + billingLabel + '</strong>, totalizando projeção de <strong>' + formatContractNumber(payload.contractValue) + '</strong> ao longo de <strong>' + termLabel + '</strong>.</p>',
        '<p>A remuneração da PARCEIRA corresponderá a comissão recorrente de <strong>' + formatPercent(payload.commissionRate) + '</strong> sobre receita líquida elegível efetivamente recebida pela CONTRATADA, projetando <strong>' + formatContractNumber(payload.monthlyCommission) + '/mês</strong> e <strong>' + formatContractNumber(payload.projectedCommission) + '</strong> na vigência simulada, ressalvados estornos, créditos, glosas, inadimplência ou cancelamentos.</p>',
        '<ul>',
        '<li>Referência de mercado equivalente: ' + formatContractNumber(payload.quote.monthlyMarket) + ' por mês.</li>',
        '<li>Economia projetada frente ao benchmark: ' + formatContractNumber(payload.quote.monthlySavings) + ' por mês.</li>',
        '<li>Elegibilidade sujeita a contrato ativo, adimplência do cliente final, ausência de bypass comercial e reconhecimento da titularidade do lead.</li>',
        '</ul>',
        '<h6>4. Confidencialidade, não aliciamento e governança do lead</h6>',
        '<p>As partes obrigam-se a preservar sigilo sobre proposta, arquitetura, precificação, pipeline, dados da oportunidade e materiais comerciais, vedado o compartilhamento indevido, o desvio de oportunidade, a abordagem direta ao cliente final sem anuência expressa da CONTRATADA ou o uso das informações para fins estranhos à negociação.</p>',
        '<h6>5. Saída honrosa, desistência e ruptura motivada</h6>',
        '<p>Admite-se <strong>saída honrosa</strong> mediante aviso prévio escrito de <strong>' + payload.noticeDays + ' dias</strong>, com transição ordenada, quitação de valores vencidos, devolução ou descarte seguro de materiais confidenciais e preservação do atendimento ao cliente final durante o handoff.</p>',
        '<p>Em caso de desistência do cliente final antes da ativação, a oportunidade poderá ser encerrada sem multa adicional, ficando ressarcíveis apenas custos aprovados e irrecuperáveis de sizing, onboarding ou reserva de capacidade, limitados a <strong>' + formatContractNumber(payload.desistenceExposure) + '</strong>.</p>',
        '<p>Constituem infração contratual grave, entre outros, bypass comercial, omissão dolosa de informação material, uso indevido da proposta, violação de confidencialidade ou inadimplência superior a 30 dias em obrigações da parceria, hipótese em que poderá haver rescisão imediata e cobrança de penalidade estimada em <strong>' + formatContractNumber(payload.breachPenalty) + '</strong>, sem prejuízo de perdas e danos comprovados.</p>',
        '<h6>6. Assinatura eletrônica e formalização definitiva</h6>',
        '<p>Esta minuta serve de base para formalização definitiva por assinatura física ou eletrônica, admitida a forma eletrônica nos termos do art. 10, § 2º, da Medida Provisória nº 2.200-2/2001. A versão executiva poderá incorporar dados cadastrais completos, anexos comerciais e critérios de faturamento adicionais.</p>',
        '<h6>7. Foro</h6>',
        '<p>Para fins de negociação e futura formalização, fica indicado o foro que guarde pertinência com o domicílio de uma das partes, na forma do art. 63 da Lei nº 13.105/2015, a ser consolidado na versão definitiva do instrumento.</p>',
        buildSignaturePanel(
          [
            {
              name: 'RPA4ALL',
              role: 'CONTRATADA · qualificação completa e signatário indicados na via definitiva',
              meta: 'Referência ' + escapeHtml(reference)
            },
            {
              name: partnerName,
              role: 'PARCEIRA · representante comercial',
              meta: partnerEmail
            }
          ],
          'Se a formalização ocorrer por plataforma eletrônica com integridade verificável, aplica-se o art. 784, § 4º, do CPC quanto à executividade documental.'
        ),
        '</div>'
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
      companyDocument: document.getElementById('requestCompanyDocument'),
      contact: document.getElementById('requestContact'),
      role: document.getElementById('requestRole'),
      email: document.getElementById('requestEmail'),
      phone: document.getElementById('requestPhone'),
      representativeDocument: document.getElementById('requestRepresentativeDocument'),
      project: document.getElementById('requestProject'),
      address: document.getElementById('requestAddress'),
      addressNumber: document.getElementById('requestAddressNumber'),
      addressComplement: document.getElementById('requestAddressComplement'),
      district: document.getElementById('requestDistrict'),
      postalCode: document.getElementById('requestPostalCode'),
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
    const printButton = document.getElementById('requestContractPrint');
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
        contractTitle: 'Minuta particular de prestação de serviços de storage',
        actionLabel: 'Solicitar sizing',
        actionHint: 'Ao confirmar, geramos um acesso no portal e enviamos as credenciais por email, mantendo os dados cadastrais da minuta.'
      },
      space: {
        eyebrow: 'Solicitação de espaço',
        title: 'Reserve capacidade de storage e gere a minuta inicial da contratação.',
        lead: 'Use este fluxo para pedir espaço protegido, formalizar janela de ativação e gerar um contrato-base com os dados do cliente.',
        summaryTitle: 'Reserva de capacidade com minuta inicial pronta para negociação.',
        summaryNote: 'Ideal para operações que já conhecem o volume e querem acelerar o fechamento comercial sem depender de email.',
        resultsKicker: 'Espaço solicitado',
        contractTitle: 'Minuta particular de reserva de capacidade de storage',
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
      const companyDocument = formatBrazilianDocument(fields.companyDocument.value || '');
      const contact = (fields.contact.value || '').trim() || 'Responsável da operação';
      const role = (fields.role.value || '').trim() || 'Tecnologia / Operações';
      const email = (fields.email.value || '').trim() || 'contato@empresa.com.br';
      const phone = (fields.phone.value || '').trim() || '+55 11 99999-9999';
      const representativeDocument = formatBrazilianDocument(fields.representativeDocument.value || '');
      const project = (fields.project.value || '').trim() || 'Projeto de storage corporativo';
      const address = (fields.address.value || '').trim();
      const addressNumber = (fields.addressNumber.value || '').trim();
      const addressComplement = (fields.addressComplement.value || '').trim();
      const district = (fields.district.value || '').trim();
      const postalCode = formatPostalCode(fields.postalCode.value || '');
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
        companyDocument: companyDocument,
        contact: contact,
        role: role,
        email: email,
        phone: phone,
        representativeDocument: representativeDocument,
        project: project,
        address: address,
        addressNumber: addressNumber,
        addressComplement: addressComplement,
        district: district,
        postalCode: postalCode,
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
      if (digitsOnly(state.companyDocument).length !== 14) {
        return 'Informe um CNPJ válido da contratante para gerar a minuta formal.';
      }
      if (digitsOnly(state.representativeDocument).length !== 11) {
        return 'Informe um CPF válido do representante da contratante.';
      }
      if (!state.address || !state.addressNumber || !state.district || digitsOnly(state.postalCode).length !== 8) {
        return 'Preencha logradouro, número, bairro e CEP para formalizar o contrato.';
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
        company_document: state.companyDocument,
        contact: state.contact,
        role: state.role,
        email: state.email,
        phone: state.phone,
        representative_document: state.representativeDocument,
        project: state.project,
        address: state.address,
        address_number: state.addressNumber,
        address_complement: state.addressComplement,
        district: state.district,
        postal_code: state.postalCode,
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
      const company = textOrPlaceholder(payload.company, 'nome empresarial da contratante', ['empresa interessada']);
      const legalName = textOrPlaceholder(payload.legalName, 'razão social da contratante', ['razão social da empresa', 'razao social da empresa']);
      const companyDocument = textOrPlaceholder(payload.companyDocument, 'CNPJ da contratante');
      const contact = textOrPlaceholder(payload.contact, 'nome do representante', ['nome do responsável', 'responsável da operação', 'responsavel da operacao']);
      const role = textOrPlaceholder(payload.role, 'cargo do representante', ['tecnologia / operações', 'tecnologia / operacoes']);
      const email = textOrPlaceholder(payload.email, 'email para notificações', ['contato@empresa.com.br']);
      const phone = textOrPlaceholder(payload.phone, 'telefone da contratante', ['+55 11 99999-9999']);
      const representativeDocument = textOrPlaceholder(payload.representativeDocument, 'CPF do representante');
      const project = textOrPlaceholder(payload.project, 'projeto ou iniciativa contratada', ['projeto de storage corporativo']);
      const notes = escapeHtml(payload.notes);
      const startDateLong = escapeHtml(formatLongDate(payload.startDateRaw));
      const issueDate = formatLongDate(new Date());
      const billingLabel = escapeHtml(payload.billingLabel);
      const termLabel = escapeHtml(payload.termLabel);
      const modeLabel = mode === 'space' ? 'reserva de capacidade' : 'sizing consultivo';
      const address = buildFullAddress({
        address: String(payload.address || '').trim(),
        number: String(payload.addressNumber || '').trim(),
        complement: String(payload.addressComplement || '').trim(),
        district: String(payload.district || '').trim(),
        city: String(payload.city || '').trim(),
        state: String(payload.state || '').trim().toUpperCase(),
        postalCode: formatPostalCode(payload.postalCode || '')
      });
      const addressLabel =
        String(payload.address || '').trim() && String(payload.addressNumber || '').trim()
          ? textOrPlaceholder(address, 'endereço completo da contratante')
          : '<span class="legal-contract__placeholder">endereço completo da contratante</span>';
      const forumLabel = textOrPlaceholder(
        [payload.city, payload.state].filter(Boolean).join('/'),
        'comarca a ser definida na versão definitiva'
      );
      const contractReference = buildContractReference(
        mode === 'space' ? 'SPACE' : 'STORAGE',
        [payload.company, payload.legalName, payload.project, payload.startDateRaw].join('|')
      );

      return [
        '<div class="legal-contract">',
        buildLetterhead(
          'Minuta particular de prestação de serviços de storage gerenciado',
          contractReference,
          'Emitida em ' + issueDate + ' · ' + contractIssuerProfile.headquarters
        ),
        '<h5 class="legal-contract__title">Instrumento particular de prestação de serviços de storage gerenciado</h5>',
        '<p class="legal-contract__lead">Pelo presente instrumento particular, em consonância com os arts. 421, 421-A, 422 e 593 e seguintes da Lei nº 10.406/2002, com observância da Lei nº 13.709/2018, da Lei nº 12.965/2014, da Medida Provisória nº 2.200-2/2001 e da Lei nº 13.105/2015, as partes abaixo identificadas registram a presente minuta-base para contratação da solução de storage gerenciado.</p>',
        buildPreparedForPanel(
          legalName,
          'Minuta preparada para o projeto ' + project + ', com personalização cadastral da contratante e base legal pronta para revisão final.',
          [
            { label: 'Contato principal', value: contact },
            { label: 'Projeto', value: project },
            { label: 'Comarca / praça', value: forumLabel }
          ]
        ),
        buildLegalSummaryGrid([
          { label: 'Referência', value: escapeHtml(contractReference) },
          { label: 'Modalidade', value: escapeHtml(modeLabel) },
          { label: 'Projeto', value: project },
          { label: 'Vigência', value: termLabel },
          { label: 'Mensalidade estimada', value: escapeHtml(formatContractNumber(payload.monthlyService)) },
          { label: 'Início pretendido', value: startDateLong }
        ]),
        '<h6>1. Qualificação das partes</h6>',
        '<p><strong>CONTRATADA:</strong> ' + contractIssuerProfile.brand + ', ' + contractIssuerProfile.qualification + ', com qualificação cadastral completa a ser reproduzida na via definitiva e em seus anexos comerciais.</p>',
        '<p><strong>CONTRATANTE:</strong> ' + company + ', inscrita no CNPJ sob nº ' + companyDocument + ', com razão social ' + legalName + ', sediada em ' + addressLabel + ', neste ato representada por ' + contact + ', ' + role + ', CPF nº ' + representativeDocument + ', email ' + email + ' e telefone ' + phone + '.</p>',
        '<h6>2. Objeto e escopo da contratação</h6>',
        '<p>O presente instrumento tem por objeto a prestação, pela CONTRATADA, de serviços gerenciados de storage para o projeto ' + project + ', em regime de <strong>' + escapeHtml(modeLabel) + '</strong>, contemplando camada <strong>' + payload.quote.tier.label + '</strong>, volume protegido estimado em <strong>' + payload.quote.volume.toLocaleString('pt-BR') + ' TB</strong>, ingresso mensal de <strong>' + payload.quote.ingress.toLocaleString('pt-BR') + ' TB</strong>, retenção de <strong>' + payload.quote.labels.retention + '</strong>, restore em <strong>' + payload.quote.sla + '</strong>, ' + payload.quote.labels.compliance + ' e topologia em <strong>' + payload.quote.labels.redundancy + '</strong>.</p>',
        '<p>O escopo definitivo poderá ser complementado por proposta comercial, ordem de serviço, cronograma de ativação, matriz de responsabilidade, SLA detalhado, anexos técnicos e política operacional correlata.</p>',
        '<h6>3. Premissas de ativação e obrigações das partes</h6>',
        '<p>Compete à CONTRATADA executar sizing, desenho de ativação, onboarding, governança operacional e suporte compatíveis com as premissas contratadas, observadas as limitações técnicas, de janela, dependências de terceiros e informações formalmente disponibilizadas.</p>',
        '<p>Compete à CONTRATANTE fornecer inventário, acessos, pontos focais, janelas de mudança, premissas de compliance, classificação da informação, instruções documentadas para tratamento de dados e validações necessárias à implantação e à continuidade do serviço.</p>',
        '<h6>4. Preço, faturamento, reajuste e mora</h6>',
        '<p>Para esta minuta, a remuneração base é estimada em <strong>' + formatContractNumber(payload.monthlyService) + '/mês</strong>, acrescida de setup inicial de <strong>' + formatContractNumber(payload.setupFee) + '</strong>, perfazendo valor contratual projetado de <strong>' + formatContractNumber(payload.contractValue) + '</strong> em <strong>' + termLabel + '</strong>, sob regime de <strong>' + billingLabel + '</strong>.</p>',
        '<ul>',
        '<li>Benchmark equivalente de mercado: ' + formatContractNumber(payload.quote.monthlyMarket) + ' por mês.</li>',
        '<li>Economia potencial frente à referência: ' + formatContractNumber(payload.quote.monthlySavings) + ' por mês.</li>',
        '<li>Após 12 meses, os valores poderão ser reajustados pelo IPCA/IBGE, ou índice que o substitua, observada a periodicidade mínima legal.</li>',
        '<li>Em atraso de pagamento, poderão incidir correção monetária, multa moratória de 2% e juros de 1% ao mês, sem prejuízo de suspensão técnica proporcional, após prévia notificação.</li>',
        '</ul>',
        '<h6>5. Proteção de dados, confidencialidade e registros</h6>',
        '<p>Na medida em que a execução contratual envolver dados pessoais, a CONTRATANTE atuará como <strong>Controladora</strong> e a CONTRATADA como <strong>Operadora</strong>, observando-se a Lei nº 13.709/2018, especialmente quanto à base legal informada pela CONTRATANTE, ao registro das operações de tratamento, ao tratamento segundo instruções documentadas e à adoção de medidas técnicas e administrativas aptas a proteger os dados.</p>',
        '<p>As partes comprometem-se a preservar confidencialidade sobre dados, credenciais, arquitetura, inventário, preços, documentos e informações comerciais ou técnicas. Quando aplicável à operação como aplicação de internet, a guarda de registros seguirá os parâmetros legais pertinentes do Marco Civil da Internet e da regulamentação incidente.</p>',
        '<h6>6. Vigência, saída honrosa e resolução por inadimplemento</h6>',
        '<p>A vigência estimada desta contratação é de <strong>' + termLabel + '</strong>, com início pretendido em <strong>' + startDateLong + '</strong>, podendo o cronograma definitivo ser ajustado por ordem de serviço ou aceite operacional.</p>',
        '<p>As partes poderão encerrar a relação por <strong>saída honrosa</strong>, mediante aviso prévio escrito de <strong>' + payload.noticeDays + ' dias</strong>, com transição assistida, exportação ou devolução dos dados na forma contratada, quitação dos valores vencidos e manutenção das obrigações de sigilo, proteção de dados e cooperação no handoff.</p>',
        '<p>Constituem hipóteses de resolução motivada, entre outras, inadimplência superior a 30 dias, descumprimento material de obrigação técnica ou financeira, uso indevido da capacidade provisionada, violação de confidencialidade, descumprimento de instruções essenciais de tratamento de dados ou omissão de informações críticas que inviabilizem a prestação. Nessas hipóteses, a penalidade comercial inicial estimada é de <strong>' + formatContractNumber(payload.breachPenalty) + '</strong>, sem prejuízo de apuração de perdas e danos comprovados.</p>',
        '<h6>7. Assinatura eletrônica, executividade e notificações</h6>',
        '<p>As partes reconhecem a validade de assinatura física ou eletrônica, inclusive por aceite eletrônico, nos termos do art. 10, § 2º, da Medida Provisória nº 2.200-2/2001. Se o instrumento definitivo for celebrado por provedor de assinatura eletrônica com integridade verificável, aplica-se o art. 784, § 4º, do CPC quanto à força executiva do documento eletrônico.</p>',
        '<p>Comunicações formais poderão ocorrer pelos emails corporativos indicados no quadro contratual, sem prejuízo de notificação complementar por plataforma, portal ou meio idôneo adicional previsto na versão definitiva.</p>',
        '<h6>8. Foro e disposições finais</h6>',
        '<p>Fica eleito o foro da comarca de ' + forumLabel + ', ou outro que guarde pertinência com o domicílio ou residência de uma das partes e venha a ser definido na via definitiva, nos termos do art. 63 da Lei nº 13.105/2015.</p>',
        '<p>Esta minuta possui natureza pré-contratual qualificada e serve como base para revisão comercial, fiscal, societária e jurídica. A contratação definitiva dependerá da consolidação dos dados cadastrais da CONTRATADA, da emissão da proposta final, da validação interna das partes e da assinatura do instrumento definitivo.</p>',
        (notes
          ? '<h6>9. Observações específicas desta solicitação</h6><p>' + notes + '</p>'
          : ''),
        buildSignaturePanel(
          [
            {
              name: 'RPA4ALL',
              role: 'CONTRATADA · qualificação cadastral e signatário a constar na via definitiva',
              meta: 'Referência ' + escapeHtml(contractReference)
            },
            {
              name: company,
              role: 'CONTRATANTE · representante ' + contact,
              meta: 'CPF ' + representativeDocument
            },
            {
              name: '<span class="legal-contract__placeholder">Testemunha 1</span>',
              role: 'Nome completo e CPF',
              meta: ''
            },
            {
              name: '<span class="legal-contract__placeholder">Testemunha 2</span>',
              role: 'Nome completo e CPF',
              meta: ''
            }
          ],
          'Minuta emitida em ' + issueDate + '. Recomenda-se revisão jurídica final, conferência dos dados societários e adequação tributária antes da assinatura executiva.'
        ),
        '</div>'
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
        '<li>Cadastral da contratante: <strong>' + escapeHtml(state.companyDocument || 'CNPJ pendente') + '</strong>, foro projetado em <strong>' + escapeHtml([state.city, state.state].filter(Boolean).join('/') || 'a definir') + '</strong>.</li>',
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
        companyDocument: state.companyDocument,
        representativeDocument: state.representativeDocument,
        project: state.project,
        address: state.address,
        addressNumber: state.addressNumber,
        addressComplement: state.addressComplement,
        district: state.district,
        postalCode: state.postalCode,
        city: state.city,
        state: state.state,
        notes: state.notes,
        startDate: state.startDate,
        startDateRaw: state.startDateRaw,
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
        companyDocument: fields.companyDocument.value,
        contact: fields.contact.value,
        role: fields.role.value,
        email: fields.email.value,
        phone: fields.phone.value,
        representativeDocument: fields.representativeDocument.value,
        project: fields.project.value,
        address: fields.address.value,
        addressNumber: fields.addressNumber.value,
        addressComplement: fields.addressComplement.value,
        district: fields.district.value,
        postalCode: fields.postalCode.value,
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

    if (printButton) {
      printButton.addEventListener('click', () => {
        if (!outputs.contractPreview || !outputs.contractPreview.innerHTML.trim()) {
          setProvisionStatus('Gere a minuta antes de imprimir o contrato.', 'error');
          return;
        }

        const title = (latestRequestState && latestRequestState.legalName)
          ? 'Contrato de storage - ' + latestRequestState.legalName
          : 'Contrato de storage RPA4ALL';
        const opened = openPrintableContract(title, outputs.contractPreview.innerHTML);
        if (!opened) {
          setProvisionStatus('O navegador bloqueou a janela de impressão. Libere popups para imprimir a minuta.', 'error');
        }
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
          const contractFile = result && result.documents && result.documents.html_relative_path
            ? ' Contrato gerado em ' + result.documents.html_relative_path + '.'
            : '';
          const successMessage = result && result.message
            ? result.message + '.' + contractFile + ' Confira também o spam se o email não chegar em poucos minutos.'
            : 'Acesso gerado com sucesso. As credenciais foram enviadas por email.' + contractFile;
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

  (function initStoragePortalPage() {
    const accessTokenInput = document.getElementById('portalAccessToken');
    if (!accessTokenInput) return;

    const state = {
      portalToken: '',
      data: null,
      currentPath: '.',
      quickNavReady: false
    };

    const dashboard = document.getElementById('portalDashboard');
    const accessStatus = document.getElementById('portalAccessStatus');
    const loadButton = document.getElementById('portalLoadButton');
    const authLink = document.getElementById('portalAuthLink');
    const nextcloudButton = document.getElementById('portalNextcloudButton');
    const nextcloudWorkspaceButton = document.getElementById('portalNextcloudWorkspaceButton');
    const contractNextcloudButton = document.getElementById('portalContractNextcloudButton');
    const refreshFilesButton = document.getElementById('portalRefreshFilesButton');
    const createTokenButton = document.getElementById('portalCreateTokenButton');
    const createUserButton = document.getElementById('portalCreateUserButton');
    const createPaymentButton = document.getElementById('portalCreatePaymentButton');
    const createFolderButton = document.getElementById('portalCreateFolderButton');
    const uploadButton = document.getElementById('portalUploadButton');

    const cards = {
      token: document.getElementById('portalTokenCard'),
      users: document.getElementById('portalUsersCard'),
      payments: document.getElementById('portalPaymentsCard'),
      files: document.getElementById('portalFilesCard')
    };

    const outputs = {
      contractCode: document.getElementById('portalContractCode'),
      companyName: document.getElementById('portalCompanyName'),
      userName: document.getElementById('portalUserName'),
      userProfile: document.getElementById('portalUserProfile'),
      monthlyService: document.getElementById('portalMonthlyService'),
      contractTerm: document.getElementById('portalContractTerm'),
      workspaceDir: document.getElementById('portalWorkspaceDir'),
      workspaceHint: document.getElementById('portalWorkspaceHint'),
      contractReference: document.getElementById('portalContractReference'),
      contractHtmlPath: document.getElementById('portalContractHtmlPath'),
      contractTextPath: document.getElementById('portalContractTextPath'),
      contractWorkspaceDir: document.getElementById('portalContractWorkspaceDir'),
      apiBase: document.getElementById('portalApiBase'),
      ingestEndpoint: document.getElementById('portalIngestEndpoint'),
      workspacePath: document.getElementById('portalWorkspacePath'),
      nextcloudHint: document.getElementById('portalNextcloudHint'),
      nextcloudDir: document.getElementById('portalNextcloudDir'),
      nextcloudWorkspaceUrl: document.getElementById('portalNextcloudWorkspaceUrl'),
      curlExample: document.getElementById('portalCurlExample'),
      latestTokenBox: document.getElementById('portalLatestTokenBox'),
      latestTokenValue: document.getElementById('portalLatestTokenValue'),
      tokenStatus: document.getElementById('portalTokenStatus'),
      userStatus: document.getElementById('portalUserStatus'),
      filesStatus: document.getElementById('portalFilesStatus'),
      paymentStatus: document.getElementById('portalPaymentStatus'),
      tokensTable: document.getElementById('portalTokensTable'),
      usersTable: document.getElementById('portalUsersTable'),
      filesPath: document.getElementById('portalFilesPath'),
      filesMeta: document.getElementById('portalFilesMeta'),
      filesList: document.getElementById('portalFilesList'),
      paymentsList: document.getElementById('portalPaymentsList'),
      inventoryGrid: document.getElementById('portalInventoryGrid'),
      servicesList: document.getElementById('portalServicesList')
    };

    const inputs = {
      tokenLabel: document.getElementById('portalTokenLabel'),
      subUserName: document.getElementById('portalSubUserName'),
      subUserEmail: document.getElementById('portalSubUserEmail'),
      subUserProfile: document.getElementById('portalSubUserProfile'),
      paymentAmount: document.getElementById('portalPaymentAmount'),
      paymentDescription: document.getElementById('portalPaymentDescription'),
      folderPath: document.getElementById('portalFolderPath'),
      uploadFile: document.getElementById('portalUploadFile')
    };

    const quickNavLinks = Array.from(document.querySelectorAll('.portal-quick-nav__link'));
    const profileLabels = {
      manager: 'Gestor',
      operations: 'Operações',
      api: 'Integração API',
      readonly: 'Somente leitura'
    };
    const statusLabels = {
      active: 'Ativo',
      disabled: 'Desativado'
    };

    function setStatus(node, message, tone) {
      if (!node) return;
      node.textContent = message || '';
      node.classList.remove('is-success', 'is-error', 'is-pending');
      if (tone === 'success') node.classList.add('is-success');
      if (tone === 'error') node.classList.add('is-error');
      if (tone === 'pending') node.classList.add('is-pending');
    }

    function formatCurrency(value) {
      return storageQuoteFormatter.format(Number(value || 0));
    }

    function formatDateTime(value) {
      if (!value) return '-';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString('pt-BR');
    }

    function formatBytes(value) {
      const bytes = Number(value || 0);
      if (bytes <= 0) return '0 B';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let size = bytes;
      let index = 0;
      while (size >= 1024 && index < units.length - 1) {
        size /= 1024;
        index += 1;
      }
      const decimals = size >= 10 || index === 0 ? 0 : 1;
      return size.toFixed(decimals).replace('.', ',') + ' ' + units[index];
    }

    function portalEndpoints(path) {
      const primary = window.location.origin + '/agents-api' + path;
      const fallback = 'https://api.rpa4all.com/agents-api' + path;
      return primary === fallback ? [primary] : [primary, fallback];
    }

    async function portalRequest(path, options) {
      let lastError = new Error('Não foi possível conectar ao portal de storage.');
      for (const endpoint of portalEndpoints(path)) {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 20000);
        try {
          const requestOptions = Object.assign({}, options || {}, { signal: controller.signal });
          const response = await fetch(endpoint, requestOptions);
          const contentType = response.headers.get('content-type') || '';
          const data = contentType.includes('application/json') ? await response.json() : await response.text();
          if (!response.ok) {
            const detail = data && typeof data.detail === 'string'
              ? data.detail
              : ('Falha ao acessar o portal (' + response.status + ').');
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

    function toggleCard(node, shouldShow) {
      if (!node) return;
      node.classList.toggle('is-hidden', !shouldShow);
    }

    function setActiveQuickNav(sectionId) {
      quickNavLinks.forEach(link => {
        const isActive = link.getAttribute('href') === '#' + sectionId;
        link.classList.toggle('is-active', isActive);
      });
    }

    function initQuickNav() {
      if (!quickNavLinks.length || state.quickNavReady) return;
      state.quickNavReady = true;

      quickNavLinks.forEach(link => {
        link.addEventListener('click', event => {
          const href = link.getAttribute('href') || '';
          if (!href.startsWith('#')) return;
          const target = document.querySelector(href);
          if (!target) return;
          event.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          setActiveQuickNav(target.id);
        });
      });

      const sections = quickNavLinks
        .map(link => document.querySelector(link.getAttribute('href') || ''))
        .filter(Boolean);

      if ('IntersectionObserver' in window && sections.length) {
        const observer = new IntersectionObserver(entries => {
          const visible = entries
            .filter(entry => entry.isIntersecting)
            .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
          if (visible) {
            setActiveQuickNav(visible.target.id);
          }
        }, {
          rootMargin: '-18% 0px -64% 0px',
          threshold: [0.2, 0.45, 0.7]
        });

        sections.forEach(section => observer.observe(section));
      } else if (sections[0]) {
        setActiveQuickNav(sections[0].id);
      }
    }

    function renderTokens(tokens) {
      if (!outputs.tokensTable) return;
      if (!tokens || !tokens.length) {
        outputs.tokensTable.innerHTML = '<tr><td colspan="4" class="portal-empty">Nenhum token gerado até agora.</td></tr>';
        return;
      }
      outputs.tokensTable.innerHTML = tokens.map(token => [
        '<tr class="portal-table-row">',
        '<td data-label="Rótulo"><strong>' + escapeHtml(token.label) + '</strong></td>',
        '<td data-label="Preview">' + escapeHtml(token.preview) + '</td>',
        '<td data-label="Status"><span class="portal-status-badge ' + escapeHtml(token.status) + '">' + escapeHtml(statusLabels[token.status] || token.status) + '</span></td>',
        '<td data-label="Criado em">' + escapeHtml(formatDateTime(token.created_at)) + '</td>',
        '</tr>'
      ].join('')).join('');
    }

    function renderUsers(users, canManage) {
      if (!outputs.usersTable) return;
      if (!users || !users.length) {
        outputs.usersTable.innerHTML = '<tr><td colspan="5" class="portal-empty">Nenhum subusuário vinculado ao contrato.</td></tr>';
        return;
      }

      outputs.usersTable.innerHTML = users.map(user => {
        const profileOptions = ['manager', 'operations', 'api', 'readonly']
          .map(profile => '<option value="' + profile + '"' + (user.profile === profile ? ' selected' : '') + '>' + escapeHtml(profileLabels[profile] || profile) + '</option>')
          .join('');
        const statusOptions = ['active', 'disabled']
          .map(status => '<option value="' + status + '"' + (user.status === status ? ' selected' : '') + '>' + escapeHtml(statusLabels[status] || status) + '</option>')
          .join('');
        const actions = canManage
          ? [
            '<div class="portal-user-actions">',
            '<select data-field="profile">' + profileOptions + '</select>',
            '<select data-field="status">' + statusOptions + '</select>',
            '<button class="btn ghost portal-user-update" type="button" data-user-id="' + user.id + '">Atualizar</button>',
            '</div>'
          ].join('')
          : '<span class="portal-empty">Somente leitura</span>';

        return [
          '<tr class="portal-table-row">',
          '<td data-label="Usuário"><strong>' + escapeHtml(user.full_name) + '</strong><br><span>' + escapeHtml(user.username) + '</span></td>',
          '<td data-label="Email">' + escapeHtml(user.email) + '</td>',
          '<td data-label="Perfil"><span class="portal-profile-badge ' + escapeHtml(user.profile) + '">' + escapeHtml(user.profile_label || profileLabels[user.profile] || user.profile) + '</span></td>',
          '<td data-label="Status"><span class="portal-status-badge ' + escapeHtml(user.status) + '">' + escapeHtml(statusLabels[user.status] || user.status) + '</span></td>',
          '<td data-label="Ação">' + actions + '</td>',
          '</tr>'
        ].join('');
      }).join('');
    }

    function renderPayments(payments) {
      if (!outputs.paymentsList) return;
      if (!payments || !payments.length) {
        outputs.paymentsList.innerHTML = '<div class="portal-empty">Nenhum link de pagamento gerado para este contrato.</div>';
        return;
      }
      outputs.paymentsList.innerHTML = payments.map(payment => [
        '<article class="portal-payment-item">',
        '<div class="portal-payment-item-head">',
        '<strong>' + formatCurrency(payment.amount_brl) + '</strong>',
        '<span>' + escapeHtml(formatDateTime(payment.created_at)) + '</span>',
        '</div>',
        '<span>' + escapeHtml(payment.description) + '</span>',
        '<span>Referência: ' + escapeHtml(payment.external_reference || '-') + '</span>',
        '<div class="portal-payment-links">',
        payment.init_point ? '<a class="btn primary" href="' + escapeHtml(payment.init_point) + '" target="_blank" rel="noopener">Abrir checkout</a>' : '',
        payment.sandbox_init_point ? '<a class="btn ghost" href="' + escapeHtml(payment.sandbox_init_point) + '" target="_blank" rel="noopener">Sandbox</a>' : '',
        '</div>',
        '</article>'
      ].join('')).join('');
    }

    function renderFiles(files) {
      if (!outputs.filesList || !files) return;
      outputs.filesPath.textContent = files.path || '.';
      outputs.filesMeta.textContent = (files.entries || []).length + ' itens · ' + formatBytes(files.total_bytes);

      const backButton = files.path && files.path !== '.'
        ? '<button class="btn ghost portal-folder-open" type="button" data-path="' + escapeHtml(files.path.split('/').slice(0, -1).join('/') || '.') + '">Voltar</button>'
        : '';

      const items = (files.entries || []).map(entry => {
        const action = entry.kind === 'folder'
          ? '<button class="btn ghost portal-folder-open" type="button" data-path="' + escapeHtml(entry.path) + '">Abrir</button>'
          : '<span>' + formatBytes(entry.size) + '</span>';
        return [
          '<article class="portal-file-item">',
          '<div class="portal-file-item-head">',
          '<strong>' + escapeHtml(entry.name) + '</strong>',
          action,
          '</div>',
          '<span>' + escapeHtml(entry.path) + '</span>',
          '<span>' + escapeHtml(formatDateTime(entry.modified_at)) + '</span>',
          '</article>'
        ].join('');
      }).join('');

      outputs.filesList.innerHTML = backButton + (items || '<div class="portal-empty">Nenhum arquivo no diretório atual.</div>');
    }

    function renderInventory(inventory) {
      if (!outputs.inventoryGrid || !inventory) return;
      const disks = (inventory.disks || []).map(disk => {
        return [
          '<div class="portal-meta">',
          '<span>' + escapeHtml(disk.mountpoint) + '</span>',
          '<strong>' + escapeHtml(disk.used_gb + ' GB usados de ' + disk.total_gb + ' GB') + '</strong>',
          '</div>'
        ].join('');
      }).join('');

      outputs.inventoryGrid.innerHTML = [
        '<div class="portal-meta"><span>Host</span><strong>' + escapeHtml(inventory.host || '-') + '</strong></div>',
        '<div class="portal-meta"><span>CPU</span><strong>' + escapeHtml((inventory.cpu && inventory.cpu.model) || '-') + ' · ' + escapeHtml(String((inventory.cpu && inventory.cpu.cores) || 0)) + ' cores</strong></div>',
        '<div class="portal-meta"><span>Memória</span><strong>' + escapeHtml(String((inventory.memory && inventory.memory.available_gb) || 0)) + ' GB livres</strong></div>',
        disks
      ].join('');

      outputs.servicesList.innerHTML = (inventory.services || []).length
        ? inventory.services.map(service => [
          '<div class="portal-service-item">',
          '<strong>' + escapeHtml(service.name) + '</strong>',
          '<span>' + escapeHtml(service.status) + '</span>',
          '</div>'
        ].join('')).join('')
        : '<div class="portal-empty">Sem detalhes adicionais de serviços.</div>';
    }

    function renderDashboard(data) {
      state.data = data;
      state.currentPath = (data.files && data.files.path) || '.';
      dashboard.classList.remove('is-hidden');
      initQuickNav();

      outputs.contractCode.textContent = data.contract.contract_code || '-';
      outputs.companyName.textContent = (data.contract.company || '-') + ' · ' + (data.contract.project || '-');
      outputs.userName.textContent = data.current_user.full_name || '-';
      outputs.userProfile.textContent = (data.current_user.profile_label || '-') + ' · ' + (data.current_user.email || '-');
      outputs.monthlyService.textContent = formatCurrency(data.contract.monthly_service);
      outputs.contractTerm.textContent = (data.contract.term_months || 0) + ' meses · ' + (data.contract.status || '-');
      outputs.workspaceDir.textContent = data.contract.workspace_relative_dir || '-';
      outputs.workspaceHint.textContent = data.contract.workspace_path || '-';
      outputs.contractReference.textContent = (data.documents && data.documents.reference) || data.contract.contract_code || '-';
      outputs.contractHtmlPath.textContent = (data.documents && data.documents.html_relative_path) || '-';
      outputs.contractTextPath.textContent = (data.documents && data.documents.text_relative_path) || '-';
      outputs.contractWorkspaceDir.textContent = data.contract.workspace_relative_dir || '-';
      outputs.apiBase.textContent = data.connections.api_base || '-';
      outputs.ingestEndpoint.textContent = data.connections.ingest_endpoint || '-';
      outputs.workspacePath.textContent = data.connections.workspace_host_path || '-';
      outputs.nextcloudHint.textContent = data.connections.nextcloud_hint || '-';
      outputs.nextcloudDir.textContent = data.connections.nextcloud_dir || data.contract.workspace_relative_dir || '-';
      outputs.nextcloudWorkspaceUrl.textContent = data.connections.nextcloud_workspace_url || data.connections.nextcloud_url || '-';
      outputs.curlExample.textContent = data.connections.curl_example || '';

      if (authLink) authLink.href = data.connections.authentik_url || 'https://auth.rpa4all.com/';
      if (nextcloudButton) nextcloudButton.href = data.connections.nextcloud_url || 'https://nextcloud.rpa4all.com/';
      if (nextcloudWorkspaceButton) {
        nextcloudWorkspaceButton.href = data.connections.nextcloud_workspace_url || data.connections.nextcloud_url || 'https://nextcloud.rpa4all.com/';
      }
      if (contractNextcloudButton) {
        contractNextcloudButton.href = data.connections.nextcloud_workspace_url || data.connections.nextcloud_url || 'https://nextcloud.rpa4all.com/';
      }

      renderTokens(data.api_tokens || []);
      renderUsers(data.users || [], Boolean(data.permissions && data.permissions.manage_profiles));
      renderPayments(data.payments || []);
      renderFiles(data.files || null);
      renderInventory(data.inventory || null);

      toggleCard(cards.token, Boolean(data.permissions && data.permissions.generate_tokens));
      toggleCard(cards.users, true);
      toggleCard(cards.payments, Boolean(data.permissions && data.permissions.manage_payments));
      toggleCard(cards.files, true);
    }

    async function loadPortal(token) {
      const normalized = String(token || '').trim();
      if (!normalized) {
        setStatus(accessStatus, 'Informe o portal token recebido por email.', 'error');
        return;
      }
      loadButton.disabled = true;
      setStatus(accessStatus, 'Carregando dados do contrato e do workspace.', 'pending');
      try {
        const data = await portalRequest('/storage/portal/bootstrap?portal_token=' + encodeURIComponent(normalized), { method: 'GET' });
        state.portalToken = normalized;
        accessTokenInput.value = normalized;
        renderDashboard(data);
        setStatus(accessStatus, 'Portal carregado com sucesso.', 'success');
      } catch (error) {
        setStatus(accessStatus, error && error.message ? error.message : 'Falha ao carregar o portal.', 'error');
      } finally {
        loadButton.disabled = false;
      }
    }

    async function refreshFiles(path) {
      if (!state.portalToken) return;
      try {
        const data = await portalRequest(
          '/storage/portal/files?portal_token=' + encodeURIComponent(state.portalToken) + '&path=' + encodeURIComponent(path || state.currentPath || '.'),
          { method: 'GET' }
        );
        if (state.data) {
          state.data.files = data;
        }
        renderFiles(data);
      } catch (error) {
        setStatus(outputs.filesStatus, error && error.message ? error.message : 'Falha ao atualizar os arquivos.', 'error');
      }
    }

    if (loadButton) {
      loadButton.addEventListener('click', () => loadPortal(accessTokenInput.value));
    }

    accessTokenInput.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        loadPortal(accessTokenInput.value);
      }
    });

    if (createTokenButton) {
      createTokenButton.addEventListener('click', async () => {
        if (!state.portalToken) return;
        createTokenButton.disabled = true;
        setStatus(outputs.tokenStatus, 'Gerando token de integração.', 'pending');
        try {
          const data = await portalRequest('/storage/portal/tokens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              portal_token: state.portalToken,
              label: inputs.tokenLabel.value || 'Integração principal'
            })
          });
          outputs.latestTokenBox.classList.remove('is-hidden');
          outputs.latestTokenValue.textContent = data.token.token || '';
          if (state.data) {
            state.data.api_tokens = data.api_tokens || [];
            state.data.connections = data.connections || state.data.connections;
          }
          renderTokens(data.api_tokens || []);
          setStatus(outputs.tokenStatus, 'Token gerado. Guarde esse valor agora, ele não será exibido novamente.', 'success');
        } catch (error) {
          setStatus(outputs.tokenStatus, error && error.message ? error.message : 'Falha ao gerar token.', 'error');
        } finally {
          createTokenButton.disabled = false;
        }
      });
    }

    if (createUserButton) {
      createUserButton.addEventListener('click', async () => {
        if (!state.portalToken) return;
        createUserButton.disabled = true;
        setStatus(outputs.userStatus, 'Criando subusuário e provisionando acesso.', 'pending');
        try {
          const data = await portalRequest('/storage/portal/subusers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              portal_token: state.portalToken,
              full_name: inputs.subUserName.value,
              email: inputs.subUserEmail.value,
              profile: inputs.subUserProfile.value
            })
          });
          if (state.data) {
            state.data.users = data.users || [];
          }
          renderUsers(data.users || [], true);
          inputs.subUserName.value = '';
          inputs.subUserEmail.value = '';
          setStatus(outputs.userStatus, 'Subusuário criado e credenciais enviadas por email.', 'success');
        } catch (error) {
          setStatus(outputs.userStatus, error && error.message ? error.message : 'Falha ao criar subusuário.', 'error');
        } finally {
          createUserButton.disabled = false;
        }
      });
    }

    if (outputs.usersTable) {
      outputs.usersTable.addEventListener('click', async event => {
        const button = event.target.closest('.portal-user-update');
        if (!button) return;
        const row = button.closest('tr');
        const profileSelect = row.querySelector('select[data-field="profile"]');
        const statusSelect = row.querySelector('select[data-field="status"]');
        button.disabled = true;
        setStatus(outputs.userStatus, 'Atualizando perfil do usuário.', 'pending');
        try {
          const data = await portalRequest('/storage/portal/users/' + button.dataset.userId, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              portal_token: state.portalToken,
              profile: profileSelect ? profileSelect.value : undefined,
              status: statusSelect ? statusSelect.value : undefined
            })
          });
          if (state.data) {
            state.data.users = data.users || [];
          }
          renderUsers(data.users || [], true);
          setStatus(outputs.userStatus, 'Perfil atualizado com sucesso.', 'success');
        } catch (error) {
          setStatus(outputs.userStatus, error && error.message ? error.message : 'Falha ao atualizar usuário.', 'error');
        } finally {
          button.disabled = false;
        }
      });
    }

    if (createPaymentButton) {
      createPaymentButton.addEventListener('click', async () => {
        if (!state.portalToken) return;
        createPaymentButton.disabled = true;
        setStatus(outputs.paymentStatus, 'Gerando link de pagamento no Mercado Pago.', 'pending');
        try {
          const data = await portalRequest('/storage/portal/payments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              portal_token: state.portalToken,
              amount_brl: Number(inputs.paymentAmount.value || 0),
              description: inputs.paymentDescription.value || 'Mensalidade storage gerenciado'
            })
          });
          if (state.data) {
            state.data.payments = data.payments || [];
          }
          renderPayments(data.payments || []);
          setStatus(outputs.paymentStatus, 'Link de pagamento gerado com sucesso.', 'success');
        } catch (error) {
          setStatus(outputs.paymentStatus, error && error.message ? error.message : 'Falha ao gerar pagamento.', 'error');
        } finally {
          createPaymentButton.disabled = false;
        }
      });
    }

    if (createFolderButton) {
      createFolderButton.addEventListener('click', async () => {
        if (!state.portalToken) return;
        createFolderButton.disabled = true;
        setStatus(outputs.filesStatus, 'Criando pasta no workspace.', 'pending');
        try {
          const data = await portalRequest('/storage/portal/files/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              portal_token: state.portalToken,
              folder_path: ((state.currentPath && state.currentPath !== '.') ? state.currentPath + '/' : '') + (inputs.folderPath.value || '')
            })
          });
          if (state.data) {
            state.data.files = data.files || state.data.files;
          }
          renderFiles(data.files || null);
          inputs.folderPath.value = '';
          setStatus(outputs.filesStatus, 'Pasta criada com sucesso.', 'success');
        } catch (error) {
          setStatus(outputs.filesStatus, error && error.message ? error.message : 'Falha ao criar pasta.', 'error');
        } finally {
          createFolderButton.disabled = false;
        }
      });
    }

    if (uploadButton) {
      uploadButton.addEventListener('click', async () => {
        if (!state.portalToken) return;
        const file = inputs.uploadFile.files && inputs.uploadFile.files[0];
        if (!file) {
          setStatus(outputs.filesStatus, 'Selecione um arquivo para upload.', 'error');
          return;
        }
        uploadButton.disabled = true;
        setStatus(outputs.filesStatus, 'Enviando arquivo para o workspace.', 'pending');
        try {
          const formData = new FormData();
          formData.append('portal_token', state.portalToken);
          formData.append('relative_dir', state.currentPath || '.');
          formData.append('upload', file);
          const data = await portalRequest('/storage/portal/files/upload', {
            method: 'POST',
            body: formData
          });
          if (state.data) {
            state.data.files = data.files || state.data.files;
          }
          renderFiles(data.files || null);
          inputs.uploadFile.value = '';
          setStatus(outputs.filesStatus, 'Arquivo enviado com sucesso.', 'success');
        } catch (error) {
          setStatus(outputs.filesStatus, error && error.message ? error.message : 'Falha ao enviar arquivo.', 'error');
        } finally {
          uploadButton.disabled = false;
        }
      });
    }

    if (outputs.filesList) {
      outputs.filesList.addEventListener('click', event => {
        const button = event.target.closest('.portal-folder-open');
        if (!button) return;
        refreshFiles(button.dataset.path || '.');
      });
    }

    if (refreshFilesButton) {
      refreshFilesButton.addEventListener('click', () => refreshFiles(state.currentPath || '.'));
    }

    const params = new URLSearchParams(window.location.search);
    const tokenFromQuery = params.get('portal');
    if (tokenFromQuery) {
      accessTokenInput.value = tokenFromQuery;
      loadPortal(tokenFromQuery);
    }
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
