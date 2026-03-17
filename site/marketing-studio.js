(function () {
  const isLocalPreview = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const sameOriginApiBase = window.location.origin.replace(/\/$/, '') + '/agents-api';
  const developmentFallbackApiBase = isLocalPreview ? 'https://api.rpa4all.com/agents-api' : '';

  const form = document.getElementById('marketingFlyerForm');
  const statusNode = document.getElementById('marketingStudioStatus');
  const imageGrid = document.getElementById('marketingImageGrid');

  if (!form || !statusNode || !imageGrid) {
    return;
  }

  const flyerPresets = {
    portrait: { width: 1080, height: 1350, label: '4:5' },
    square: { width: 1080, height: 1080, label: '1:1' },
    story: { width: 1080, height: 1920, label: '9:16' }
  };

  const profileNodes = {
    name: document.getElementById('marketingProfileName'),
    email: document.getElementById('marketingProfileEmail'),
    username: document.getElementById('marketingProfileUsername'),
    role: document.getElementById('marketingProfileRole'),
    hint: document.getElementById('marketingProfileHint')
  };

  const flyerNodes = {
    headline: document.getElementById('marketingFlyerHeadline'),
    subheadline: document.getElementById('marketingFlyerSubheadline'),
    intro: document.getElementById('marketingFlyerIntro'),
    bullets: document.getElementById('marketingFlyerBullets'),
    primaryCta: document.getElementById('marketingFlyerPrimaryCta'),
    secondaryCta: document.getElementById('marketingFlyerSecondaryCta'),
    source: document.getElementById('marketingStudioSource')
  };

  const agentNodes = {
    researchSource: document.getElementById('marketingResearchSource'),
    researchContext: document.getElementById('marketingResearchContext'),
    researchPoints: document.getElementById('marketingResearchPoints'),
    researchKeywords: document.getElementById('marketingResearchKeywords'),
    reasoningSource: document.getElementById('marketingReasoningSource'),
    reasoningPositioning: document.getElementById('marketingReasoningPositioning'),
    reasoningPoints: document.getElementById('marketingReasoningPoints'),
    reasoningLayout: document.getElementById('marketingReasoningLayout'),
    offerSource: document.getElementById('marketingOfferSource'),
    offerVisualDirection: document.getElementById('marketingOfferVisualDirection'),
    offerCanvasPrompt: document.getElementById('marketingOfferCanvasPrompt')
  };

  const flyerControlNodes = {
    preset: document.getElementById('marketingCanvasPreset'),
    layer: document.getElementById('marketingCanvasLayer'),
    x: document.getElementById('marketingCanvasX'),
    y: document.getElementById('marketingCanvasY'),
    scale: document.getElementById('marketingCanvasScale'),
    opacity: document.getElementById('marketingCanvasOpacity'),
    selection: document.getElementById('marketingCanvasSelection'),
    reset: document.getElementById('marketingCanvasReset'),
    download: document.getElementById('marketingCanvasDownload')
  };

  const cardFields = {
    name: document.getElementById('businessCardName'),
    title: document.getElementById('businessCardTitle'),
    email: document.getElementById('businessCardEmail'),
    phone: document.getElementById('businessCardPhone'),
    tagline: document.getElementById('businessCardTagline'),
    specialties: document.getElementById('businessCardSpecialties'),
    note: document.getElementById('businessCardNote')
  };

  const businessControlNodes = {
    side: document.getElementById('businessCardEditorSide'),
    layer: document.getElementById('businessCardLayer'),
    x: document.getElementById('businessCardX'),
    y: document.getElementById('businessCardY'),
    scale: document.getElementById('businessCardScale'),
    opacity: document.getElementById('businessCardOpacity'),
    selection: document.getElementById('businessCardSelection'),
    downloadFront: document.getElementById('businessCardDownloadFront'),
    downloadBack: document.getElementById('businessCardDownloadBack'),
    print: document.getElementById('businessCardPrint')
  };

  const studioState = {
    payload: createFallbackPayload(),
    images: [],
    selectedImageIndex: -1
  };

  const flyerEditor = createCanvasEditor(document.getElementById('marketingArtboardCanvas'));
  const businessFrontEditor = createCanvasEditor(document.getElementById('businessCardFrontCanvas'));
  const businessBackEditor = createCanvasEditor(document.getElementById('businessCardBackCanvas'));

  function createFallbackPayload() {
    return {
      brief: {
        headline: 'Aguardando geração',
        subheadline: 'Informe um tema para montar headline, posicionamento e canvas.',
        intro: 'O estúdio agora gera uma composição editável em canvas para flyer e cartão de visita.',
        offer_bullets: ['Automação', 'IA aplicada', 'Observabilidade', 'Storage gerenciado'],
        cta_primary: 'Solicitar sizing',
        cta_secondary: 'Falar com comercial',
        business_card_tagline: 'Automação inteligente, observabilidade e IA aplicada',
        business_card_back_note: 'Automação, IA aplicada e observabilidade para operações exigentes.',
        visual_direction: 'Fotografia corporativa, interface limpa e contraste alto.',
        canvas_prompt: 'Headline forte, imagem de contexto e CTA claro.'
      },
      research: {
        market_context: 'O agente de pesquisa será executado após informar um tema.',
        pain_points: ['retrabalho operacional', 'baixa previsibilidade', 'processos manuais'],
        visual_keywords: ['equipe', 'operação', 'tecnologia'],
        color_hint: 'azul petróleo, ciano e verde'
      },
      reasoning: {
        positioning: 'O agente de raciocínio vai converter a pesquisa em mensagem comercial.',
        proof_points: ['automação', 'IA aplicada', 'observabilidade'],
        flyer_layout: 'headline à esquerda e imagem em destaque'
      },
      agent_sources: {
        research: 'aguardando',
        reasoning: 'aguardando',
        brief: 'aguardando'
      },
      image_research: {
        items: []
      },
      narrative_source: 'aguardando'
    };
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fetchJson(url, options) {
    return fetch(url, options || { headers: { Accept: 'application/json' } }).then(function (response) {
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }
      return response.json();
    });
  }

  function setStatus(message, mode) {
    statusNode.textContent = message;
    statusNode.dataset.mode = mode || 'info';
  }

  function listToHtml(items) {
    if (!items || !items.length) {
      return '<li>Nenhum dado retornado.</li>';
    }
    return items.map(function (item) {
      return '<li>' + escapeHtml(item) + '</li>';
    }).join('');
  }

  function badgeListToHtml(items) {
    if (!items || !items.length) {
      return '<span>Sem palavras-chave</span>';
    }
    return items.map(function (item) {
      return '<span>' + escapeHtml(item) + '</span>';
    }).join('');
  }

  function createCanvasEditor(canvas) {
    if (!canvas || !canvas.getContext) {
      return null;
    }

    const editor = {
      canvas: canvas,
      ctx: canvas.getContext('2d'),
      scene: { width: canvas.width || 1, height: canvas.height || 1, background: {}, layers: [] },
      layers: [],
      activeLayerId: '',
      dragState: null,
      onSelectionChange: null,
      onSceneChange: null
    };

    canvas.addEventListener('pointerdown', function (event) {
      const point = getCanvasPoint(canvas, event);
      const hitLayer = findHitLayer(editor, point.x, point.y);
      if (!hitLayer) {
        return;
      }

      editor.activeLayerId = hitLayer.id;
      editor.dragState = {
        pointerId: event.pointerId,
        layerId: hitLayer.id,
        offsetX: point.x - hitLayer.x,
        offsetY: point.y - hitLayer.y
      };

      canvas.setPointerCapture(event.pointerId);
      drawEditor(editor);
      notifyEditorSelection(editor);
    });

    canvas.addEventListener('pointermove', function (event) {
      if (!editor.dragState || event.pointerId !== editor.dragState.pointerId) {
        return;
      }

      const layer = getLayerById(editor, editor.dragState.layerId);
      if (!layer || !layer.bbox) {
        return;
      }

      const point = getCanvasPoint(canvas, event);
      const maxX = Math.max(0, editor.canvas.width - layer.bbox.width);
      const maxY = Math.max(0, editor.canvas.height - layer.bbox.height);
      layer.x = clamp(point.x - editor.dragState.offsetX, 0, maxX);
      layer.y = clamp(point.y - editor.dragState.offsetY, 0, maxY);
      drawEditor(editor);
      notifyEditorSelection(editor);
      if (typeof editor.onSceneChange === 'function') {
        editor.onSceneChange(editor);
      }
    });

    function releasePointer(event) {
      if (!editor.dragState || event.pointerId !== editor.dragState.pointerId) {
        return;
      }
      editor.dragState = null;
      if (typeof editor.onSceneChange === 'function') {
        editor.onSceneChange(editor);
      }
    }

    canvas.addEventListener('pointerup', releasePointer);
    canvas.addEventListener('pointercancel', releasePointer);

    return editor;
  }

  function getCanvasPoint(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
    return { x: x, y: y };
  }

  function findHitLayer(editor, x, y) {
    for (let index = editor.layers.length - 1; index >= 0; index -= 1) {
      const layer = editor.layers[index];
      if (layer.editable === false || !layer.bbox) {
        continue;
      }
      if (
        x >= layer.bbox.x &&
        x <= layer.bbox.x + layer.bbox.width &&
        y >= layer.bbox.y &&
        y <= layer.bbox.y + layer.bbox.height
      ) {
        return layer;
      }
    }
    return null;
  }

  function getLayerById(editor, layerId) {
    return editor.layers.find(function (item) {
      return item.id === layerId;
    }) || null;
  }

  function getEditableLayers(editor) {
    return editor.layers.filter(function (layer) {
      return layer.editable !== false;
    });
  }

  function notifyEditorSelection(editor) {
    if (typeof editor.onSelectionChange === 'function') {
      editor.onSelectionChange(editor);
    }
  }

  function setEditorScene(editor, scene) {
    if (!editor || !editor.ctx) {
      return;
    }

    editor.scene = scene;
    editor.canvas.width = scene.width;
    editor.canvas.height = scene.height;
    editor.layers = scene.layers.map(function (layer) {
      const copy = Object.assign({}, layer);
      copy.opacity = typeof copy.opacity === 'number' ? copy.opacity : 1;
      copy.scale = typeof copy.scale === 'number' ? copy.scale : 1;
      copy.bbox = null;
      copy.imageObject = null;
      copy.imageLoaded = false;
      copy.imageError = false;
      if (copy.type === 'image' && copy.src) {
        loadLayerImage(copy, editor);
      }
      return copy;
    });

    const editableLayers = getEditableLayers(editor);
    editor.activeLayerId = editableLayers.length ? editableLayers[0].id : '';
    drawEditor(editor);
    notifyEditorSelection(editor);
  }

  function loadLayerImage(layer, editor) {
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = function () {
      layer.imageObject = image;
      layer.imageLoaded = true;
      drawEditor(editor);
    };
    image.onerror = function () {
      layer.imageError = true;
      drawEditor(editor);
    };
    image.src = layer.src;
  }

  function drawEditor(editor) {
    if (!editor || !editor.ctx) {
      return;
    }

    const ctx = editor.ctx;
    const width = editor.canvas.width;
    const height = editor.canvas.height;

    ctx.clearRect(0, 0, width, height);
    drawSceneBackground(ctx, width, height, editor.scene.background || {});

    editor.layers.forEach(function (layer) {
      layer.bbox = null;
      switch (layer.type) {
        case 'panel':
          drawPanelLayer(ctx, layer);
          break;
        case 'image':
          drawImageLayer(ctx, layer);
          break;
        case 'badge':
          drawBadgeLayer(ctx, layer);
          break;
        case 'button':
          drawButtonLayer(ctx, layer);
          break;
        case 'chips':
          drawChipLayer(ctx, layer);
          break;
        case 'text':
        default:
          drawTextLayer(ctx, layer);
          break;
      }
    });

    const activeLayer = getLayerById(editor, editor.activeLayerId);
    if (activeLayer && activeLayer.bbox) {
      ctx.save();
      ctx.strokeStyle = 'rgba(125, 211, 252, 0.95)';
      ctx.lineWidth = 4;
      ctx.setLineDash([12, 10]);
      ctx.strokeRect(
        activeLayer.bbox.x - 10,
        activeLayer.bbox.y - 10,
        activeLayer.bbox.width + 20,
        activeLayer.bbox.height + 20
      );
      ctx.restore();
    }
  }

  function drawSceneBackground(ctx, width, height, background) {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, background.start || '#06111c');
    gradient.addColorStop(0.58, background.mid || '#0c2238');
    gradient.addColorStop(1, background.end || '#0c5136');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    const glowA = background.glowA || 'rgba(56, 189, 248, 0.25)';
    const glowB = background.glowB || 'rgba(34, 197, 94, 0.18)';

    ctx.save();
    ctx.fillStyle = glowA;
    ctx.beginPath();
    ctx.arc(width * 0.82, height * 0.18, width * 0.24, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = glowB;
    ctx.beginPath();
    ctx.arc(width * 0.14, height * 0.82, width * 0.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= width; x += Math.round(width / 10)) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y <= height; y += Math.round(height / 12)) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function roundedRectPath(ctx, x, y, width, height, radius) {
    const safeRadius = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + safeRadius, y);
    ctx.lineTo(x + width - safeRadius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
    ctx.lineTo(x + width, y + height - safeRadius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
    ctx.lineTo(x + safeRadius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
    ctx.lineTo(x, y + safeRadius);
    ctx.quadraticCurveTo(x, y, x + safeRadius, y);
    ctx.closePath();
  }

  function drawPanelLayer(ctx, layer) {
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    roundedRectPath(ctx, layer.x, layer.y, layer.width, layer.height, layer.radius || 24);
    ctx.fillStyle = layer.fill || 'rgba(5, 15, 28, 0.74)';
    ctx.fill();
    if (layer.stroke) {
      ctx.strokeStyle = layer.stroke;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.restore();
    layer.bbox = { x: layer.x, y: layer.y, width: layer.width, height: layer.height };
  }

  function drawImageLayer(ctx, layer) {
    const width = layer.width * layer.scale;
    const height = layer.height * layer.scale;
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    roundedRectPath(ctx, layer.x, layer.y, width, height, layer.radius || 28);
    ctx.clip();

    if (layer.imageLoaded && layer.imageObject) {
      const image = layer.imageObject;
      const ratio = Math.max(width / image.width, height / image.height);
      const drawWidth = image.width * ratio;
      const drawHeight = image.height * ratio;
      const drawX = layer.x + (width - drawWidth) / 2;
      const drawY = layer.y + (height - drawHeight) / 2;
      ctx.drawImage(image, drawX, drawY, drawWidth, drawHeight);
    } else {
      const placeholder = ctx.createLinearGradient(layer.x, layer.y, layer.x + width, layer.y + height);
      placeholder.addColorStop(0, 'rgba(14, 165, 233, 0.28)');
      placeholder.addColorStop(1, 'rgba(34, 197, 94, 0.18)');
      ctx.fillStyle = placeholder;
      ctx.fillRect(layer.x, layer.y, width, height);
      ctx.fillStyle = 'rgba(230, 238, 248, 0.72)';
      ctx.font = '600 24px Inter, system-ui, sans-serif';
      ctx.fillText(layer.placeholder || 'Imagem para composição', layer.x + 28, layer.y + 48);
    }

    ctx.fillStyle = 'rgba(6, 16, 29, 0.16)';
    ctx.fillRect(layer.x, layer.y, width, height);
    ctx.restore();

    layer.bbox = { x: layer.x, y: layer.y, width: width, height: height };
  }

  function drawBadgeLayer(ctx, layer) {
    const width = layer.width * layer.scale;
    const height = layer.height * layer.scale;
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    roundedRectPath(ctx, layer.x, layer.y, width, height, layer.radius || 18);
    ctx.fillStyle = layer.fill || '#22c55e';
    ctx.fill();
    ctx.fillStyle = layer.color || '#041018';
    ctx.font = (layer.weight || 800) + ' ' + Math.round((layer.fontSize || 30) * layer.scale) + 'px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(layer.text || '', layer.x + width / 2, layer.y + height / 2 + 2);
    ctx.restore();
    layer.bbox = { x: layer.x, y: layer.y, width: width, height: height };
  }

  function wrapText(ctx, text, maxWidth) {
    const raw = String(text || '').split(/\n+/);
    const lines = [];

    raw.forEach(function (paragraph) {
      const words = paragraph.split(/\s+/).filter(Boolean);
      if (!words.length) {
        lines.push('');
        return;
      }
      let current = words[0];
      for (let index = 1; index < words.length; index += 1) {
        const next = current + ' ' + words[index];
        if (ctx.measureText(next).width <= maxWidth) {
          current = next;
        } else {
          lines.push(current);
          current = words[index];
        }
      }
      lines.push(current);
    });

    return lines;
  }

  function drawTextLayer(ctx, layer) {
    const fontSize = Math.round((layer.fontSize || 34) * layer.scale);
    const maxWidth = Math.max(40, (layer.width || 300) * layer.scale);
    const lineHeight = Math.round(fontSize * (layer.lineHeight || 1.18));
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    ctx.fillStyle = layer.color || '#f8fbff';
    ctx.font = (layer.weight || 600) + ' ' + fontSize + 'px Inter, system-ui, sans-serif';
    ctx.textAlign = layer.align || 'left';
    ctx.textBaseline = 'top';

    const lines = wrapText(ctx, layer.text || '', maxWidth);
    lines.forEach(function (line, index) {
      const x = layer.align === 'center' ? layer.x + maxWidth / 2 : layer.x;
      ctx.fillText(line, x, layer.y + index * lineHeight);
    });
    ctx.restore();

    layer.bbox = {
      x: layer.x,
      y: layer.y,
      width: maxWidth,
      height: Math.max(lineHeight, lines.length * lineHeight)
    };
  }

  function drawButtonLayer(ctx, layer) {
    const width = (layer.width || 260) * layer.scale;
    const height = (layer.height || 64) * layer.scale;
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    roundedRectPath(ctx, layer.x, layer.y, width, height, layer.radius || 999);
    ctx.fillStyle = layer.fill || '#22c55e';
    ctx.fill();
    ctx.fillStyle = layer.color || '#041018';
    ctx.font = (layer.weight || 700) + ' ' + Math.round((layer.fontSize || 28) * layer.scale) + 'px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(layer.text || '', layer.x + width / 2, layer.y + height / 2 + 2);
    ctx.restore();
    layer.bbox = { x: layer.x, y: layer.y, width: width, height: height };
  }

  function drawChipLayer(ctx, layer) {
    const items = Array.isArray(layer.items) ? layer.items : [];
    const maxWidth = (layer.width || 360) * layer.scale;
    const fontSize = Math.round((layer.fontSize || 22) * layer.scale);
    const gap = Math.round(14 * layer.scale);
    const paddingX = Math.round(18 * layer.scale);
    const paddingY = Math.round(12 * layer.scale);
    const radius = Math.round(999 * layer.scale);
    let cursorX = layer.x;
    let cursorY = layer.y;
    let rowHeight = 0;
    let maxLineWidth = 0;

    ctx.save();
    ctx.globalAlpha = layer.opacity;
    ctx.font = (layer.weight || 700) + ' ' + fontSize + 'px Inter, system-ui, sans-serif';
    ctx.textBaseline = 'middle';

    items.forEach(function (item) {
      const text = String(item || '').trim();
      if (!text) {
        return;
      }

      const chipWidth = Math.round(ctx.measureText(text).width + paddingX * 2);
      const chipHeight = fontSize + paddingY * 2;
      if (cursorX > layer.x && cursorX + chipWidth > layer.x + maxWidth) {
        cursorX = layer.x;
        cursorY += rowHeight + gap;
        rowHeight = 0;
      }

      roundedRectPath(ctx, cursorX, cursorY, chipWidth, chipHeight, radius);
      ctx.fillStyle = layer.fill || 'rgba(14, 165, 233, 0.18)';
      ctx.fill();
      ctx.fillStyle = layer.color || '#dff7ff';
      ctx.fillText(text, cursorX + paddingX, cursorY + chipHeight / 2);

      rowHeight = Math.max(rowHeight, chipHeight);
      maxLineWidth = Math.max(maxLineWidth, cursorX + chipWidth - layer.x);
      cursorX += chipWidth + gap;
    });

    ctx.restore();

    layer.bbox = {
      x: layer.x,
      y: layer.y,
      width: Math.max(180, maxLineWidth),
      height: Math.max(42, cursorY - layer.y + rowHeight)
    };
  }

  function syncEditorControls(editor, nodes) {
    if (!editor || !nodes.layer) {
      return;
    }

    const editableLayers = getEditableLayers(editor);
    nodes.layer.innerHTML = editableLayers.map(function (layer) {
      return '<option value="' + escapeHtml(layer.id) + '">' + escapeHtml(layer.label || layer.id) + '</option>';
    }).join('');

    if (!editableLayers.length) {
      return;
    }

    let activeLayer = getLayerById(editor, editor.activeLayerId);
    if (!activeLayer || activeLayer.editable === false) {
      activeLayer = editableLayers[0];
      editor.activeLayerId = activeLayer.id;
    }

    nodes.layer.value = activeLayer.id;
    nodes.selection.textContent = activeLayer.label || activeLayer.id;
    nodes.x.max = String(editor.canvas.width);
    nodes.y.max = String(editor.canvas.height);
    nodes.x.value = String(Math.round(activeLayer.x || 0));
    nodes.y.value = String(Math.round(activeLayer.y || 0));
    nodes.scale.value = String(Math.round((activeLayer.scale || 1) * 100));
    nodes.opacity.value = String(Math.round((typeof activeLayer.opacity === 'number' ? activeLayer.opacity : 1) * 100));
  }

  function bindEditorControls(nodes, getEditor) {
    if (!nodes.layer) {
      return;
    }

    nodes.layer.addEventListener('change', function () {
      const editor = getEditor();
      if (!editor) {
        return;
      }
      editor.activeLayerId = nodes.layer.value;
      drawEditor(editor);
      syncEditorControls(editor, nodes);
    });

    function updateLayer(applyChange) {
      const editor = getEditor();
      if (!editor) {
        return;
      }
      const layer = getLayerById(editor, editor.activeLayerId);
      if (!layer) {
        return;
      }
      applyChange(layer, editor);
      drawEditor(editor);
      syncEditorControls(editor, nodes);
      if (typeof editor.onSceneChange === 'function') {
        editor.onSceneChange(editor);
      }
    }

    nodes.x.addEventListener('input', function () {
      updateLayer(function (layer, editor) {
        const limit = Math.max(0, editor.canvas.width - ((layer.bbox && layer.bbox.width) || 0));
        layer.x = clamp(Number(nodes.x.value), 0, limit);
      });
    });

    nodes.y.addEventListener('input', function () {
      updateLayer(function (layer, editor) {
        const limit = Math.max(0, editor.canvas.height - ((layer.bbox && layer.bbox.height) || 0));
        layer.y = clamp(Number(nodes.y.value), 0, limit);
      });
    });

    nodes.scale.addEventListener('input', function () {
      updateLayer(function (layer) {
        layer.scale = clamp(Number(nodes.scale.value) / 100, 0.5, 1.8);
      });
    });

    nodes.opacity.addEventListener('input', function () {
      updateLayer(function (layer) {
        layer.opacity = clamp(Number(nodes.opacity.value) / 100, 0.1, 1);
      });
    });
  }

  function getSelectedImage() {
    return studioState.images[studioState.selectedImageIndex] || null;
  }

  function getCardData() {
    return {
      name: (cardFields.name.value || 'Seu nome').trim(),
      title: (cardFields.title.value || 'Especialista RPA4ALL').trim(),
      email: (cardFields.email.value || 'voce@rpa4all.com').trim(),
      phone: (cardFields.phone.value || '+55 11 99999-0000').trim(),
      tagline: (cardFields.tagline.value || 'Automação inteligente, observabilidade e IA aplicada').trim(),
      specialties: (cardFields.specialties.value || 'Storage gerenciado • IA aplicada • observabilidade').trim(),
      note: (cardFields.note.value || 'Automação, IA aplicada e observabilidade para operações exigentes.').trim()
    };
  }

  function buildFlyerScene(payload, presetKey, selectedImage) {
    const preset = flyerPresets[presetKey] || flyerPresets.portrait;
    const brief = payload.brief || {};
    const research = payload.research || {};
    const gutter = Math.round(preset.width * 0.06);
    const panelWidth = Math.round(preset.width * 0.47);
    const textX = gutter + 42;
    const textWidth = panelWidth - 84;
    const imageWidth = preset.width - panelWidth - gutter * 2;
    const imageX = preset.width - imageWidth - gutter;
    const imageY = gutter;
    const imageHeight = preset.height - gutter * 2;

    return {
      width: preset.width,
      height: preset.height,
      background: {
        start: '#06101d',
        mid: '#0b1f33',
        end: '#0f5132',
        glowA: 'rgba(56, 189, 248, 0.24)',
        glowB: 'rgba(34, 197, 94, 0.18)'
      },
      layers: [
        {
          id: 'image',
          label: 'Imagem principal',
          type: 'image',
          x: imageX,
          y: imageY,
          width: imageWidth,
          height: imageHeight,
          radius: 34,
          src: selectedImage ? selectedImage.image_url : '',
          placeholder: selectedImage ? (selectedImage.title || 'Imagem selecionada') : 'Escolha uma imagem da pesquisa visual',
          scale: 1,
          opacity: 1
        },
        {
          id: 'panel',
          label: 'Painel de apoio',
          type: 'panel',
          editable: false,
          x: gutter,
          y: gutter,
          width: panelWidth,
          height: preset.height - gutter * 2,
          radius: 34,
          fill: 'rgba(4, 11, 22, 0.72)',
          stroke: 'rgba(125, 211, 252, 0.12)',
          opacity: 1
        },
        {
          id: 'kicker',
          label: 'Kicker',
          type: 'text',
          x: textX,
          y: gutter + 42,
          width: textWidth,
          fontSize: 22,
          weight: 700,
          color: '#7dd3fc',
          text: 'RPA4ALL • ' + (brief.audience_label || 'Estúdio comercial'),
          editable: false
        },
        {
          id: 'headline',
          label: 'Headline',
          type: 'text',
          x: textX,
          y: gutter + 88,
          width: textWidth,
          fontSize: presetKey === 'story' ? 76 : 68,
          weight: 800,
          color: '#f8fbff',
          lineHeight: 1.02,
          text: brief.headline || 'Oferta RPA4ALL',
          scale: 1
        },
        {
          id: 'subheadline',
          label: 'Subheadline',
          type: 'text',
          x: textX,
          y: gutter + 338,
          width: textWidth,
          fontSize: 28,
          weight: 500,
          color: 'rgba(230, 238, 248, 0.92)',
          lineHeight: 1.22,
          text: brief.subheadline || '',
          scale: 1
        },
        {
          id: 'intro',
          label: 'Texto de apoio',
          type: 'text',
          x: textX,
          y: gutter + 458,
          width: textWidth,
          fontSize: 23,
          weight: 400,
          color: 'rgba(220, 232, 244, 0.84)',
          lineHeight: 1.36,
          text: brief.intro || '',
          scale: 1
        },
        {
          id: 'bullets',
          label: 'Pílulas de valor',
          type: 'chips',
          x: textX,
          y: preset.height - gutter - 250,
          width: textWidth,
          fontSize: 20,
          weight: 700,
          fill: 'rgba(14, 165, 233, 0.16)',
          color: '#dff7ff',
          items: brief.offer_bullets || []
        },
        {
          id: 'cta',
          label: 'CTA',
          type: 'button',
          x: textX,
          y: preset.height - gutter - 96,
          width: 310,
          height: 68,
          fill: '#22c55e',
          color: '#041018',
          fontSize: 28,
          weight: 800,
          text: brief.cta_primary || 'Solicitar proposta',
          scale: 1
        },
        {
          id: 'visual-note',
          label: 'Direção visual',
          type: 'text',
          x: imageX + 34,
          y: preset.height - gutter - 92,
          width: Math.max(220, imageWidth - 68),
          fontSize: 22,
          weight: 600,
          color: '#f8fbff',
          text: brief.visual_direction || research.image_style || 'Direção visual',
          opacity: 0.92
        }
      ]
    };
  }

  function buildBusinessCardScene(side, payload, selectedImage) {
    const cardData = getCardData();
    const brief = payload.brief || {};
    const baseLayers = [
      {
        id: 'watermark',
        label: 'Imagem de fundo',
        type: 'image',
        x: 0,
        y: 0,
        width: 1050,
        height: 600,
        src: selectedImage ? selectedImage.image_url : '',
        placeholder: 'Sem imagem aplicada',
        opacity: selectedImage ? 0.18 : 0.08,
        scale: 1
      },
      {
        id: 'overlay',
        label: 'Painel',
        type: 'panel',
        editable: false,
        x: 24,
        y: 24,
        width: 1002,
        height: 552,
        radius: 28,
        fill: side === 'front' ? 'rgba(6, 16, 29, 0.84)' : 'rgba(7, 24, 44, 0.86)',
        stroke: 'rgba(255, 255, 255, 0.08)',
        opacity: 1
      }
    ];

    if (side === 'front') {
      return {
        width: 1050,
        height: 600,
        background: {
          start: '#07111f',
          mid: '#0c2238',
          end: '#0f5132'
        },
        layers: baseLayers.concat([
          {
            id: 'logo',
            label: 'Logo',
            type: 'badge',
            x: 68,
            y: 70,
            width: 110,
            height: 110,
            radius: 28,
            fill: '#22c55e',
            color: '#041018',
            fontSize: 42,
            text: 'R4',
            scale: 1
          },
          {
            id: 'brand',
            label: 'Marca',
            type: 'text',
            x: 206,
            y: 84,
            width: 260,
            fontSize: 28,
            weight: 700,
            color: '#7dd3fc',
            text: 'RPA4ALL',
            scale: 1
          },
          {
            id: 'name',
            label: 'Nome',
            type: 'text',
            x: 68,
            y: 230,
            width: 620,
            fontSize: 62,
            weight: 800,
            color: '#f8fbff',
            lineHeight: 1.04,
            text: cardData.name,
            scale: 1
          },
          {
            id: 'title',
            label: 'Cargo',
            type: 'text',
            x: 68,
            y: 346,
            width: 620,
            fontSize: 30,
            weight: 600,
            color: '#c8e8f7',
            text: cardData.title,
            scale: 1
          },
          {
            id: 'tagline',
            label: 'Assinatura',
            type: 'text',
            x: 68,
            y: 418,
            width: 660,
            fontSize: 24,
            weight: 400,
            color: 'rgba(220, 232, 244, 0.88)',
            lineHeight: 1.28,
            text: cardData.tagline || brief.business_card_tagline || '',
            scale: 1
          },
          {
            id: 'site',
            label: 'Website',
            type: 'text',
            x: 740,
            y: 508,
            width: 240,
            fontSize: 24,
            weight: 700,
            color: '#86efac',
            text: 'www.rpa4all.com',
            scale: 1
          }
        ])
      };
    }

    return {
      width: 1050,
      height: 600,
      background: {
        start: '#06111c',
        mid: '#0b1f33',
        end: '#0a3552'
      },
      layers: baseLayers.concat([
        {
          id: 'brand',
          label: 'Marca',
          type: 'text',
          x: 72,
          y: 76,
          width: 260,
          fontSize: 42,
          weight: 800,
          color: '#f8fbff',
          text: 'RPA4ALL',
          scale: 1
        },
        {
          id: 'contact',
          label: 'Contatos',
          type: 'text',
          x: 72,
          y: 178,
          width: 430,
          fontSize: 28,
          weight: 500,
          color: '#dce8f4',
          lineHeight: 1.45,
          text: [cardData.email, cardData.phone, 'www.rpa4all.com'].join('\n'),
          scale: 1
        },
        {
          id: 'specialties',
          label: 'Especialidades',
          type: 'text',
          x: 560,
          y: 178,
          width: 410,
          fontSize: 24,
          weight: 600,
          color: '#dff7ff',
          lineHeight: 1.35,
          text: cardData.specialties,
          scale: 1
        },
        {
          id: 'note',
          label: 'Mensagem curta',
          type: 'text',
          x: 72,
          y: 430,
          width: 898,
          fontSize: 22,
          weight: 400,
          color: 'rgba(220, 232, 244, 0.84)',
          lineHeight: 1.28,
          text: cardData.note || brief.business_card_back_note || '',
          scale: 1
        }
      ])
    };
  }

  function renderBrief(payload) {
    const brief = payload.brief || {};
    flyerNodes.headline.textContent = brief.headline || 'Panfleto gerado';
    flyerNodes.subheadline.textContent = brief.subheadline || '';
    flyerNodes.intro.textContent = brief.intro || '';
    flyerNodes.bullets.innerHTML = (brief.offer_bullets || []).map(function (item) {
      return '<span>' + escapeHtml(item) + '</span>';
    }).join('');
    flyerNodes.primaryCta.textContent = brief.cta_primary || 'Solicitar proposta';
    flyerNodes.secondaryCta.textContent = brief.cta_secondary || 'Falar com comercial';
    flyerNodes.source.textContent = (payload.narrative_source || 'fallback') + (brief._ollama_model ? ' • ' + brief._ollama_model : '');

    if (!cardFields.tagline.value && brief.business_card_tagline) {
      cardFields.tagline.value = brief.business_card_tagline;
    }
    if (!cardFields.note.value && brief.business_card_back_note) {
      cardFields.note.value = brief.business_card_back_note;
    }
  }

  function renderAgents(payload) {
    const research = payload.research || {};
    const reasoning = payload.reasoning || {};
    const brief = payload.brief || {};
    const sources = payload.agent_sources || {};

    agentNodes.researchSource.textContent = sources.research || 'fallback';
    agentNodes.researchContext.textContent = research.market_context || 'Sem contexto retornado.';
    agentNodes.researchPoints.innerHTML = listToHtml(research.pain_points || []);
    agentNodes.researchKeywords.innerHTML = badgeListToHtml(research.visual_keywords || []);

    agentNodes.reasoningSource.textContent = sources.reasoning || 'fallback';
    agentNodes.reasoningPositioning.textContent = reasoning.positioning || 'Sem posicionamento retornado.';
    agentNodes.reasoningPoints.innerHTML = listToHtml(reasoning.proof_points || []);
    agentNodes.reasoningLayout.textContent = reasoning.flyer_layout || 'Layout ainda não definido.';

    agentNodes.offerSource.textContent = sources.brief || 'fallback';
    agentNodes.offerVisualDirection.textContent = brief.visual_direction || 'Sem direção visual retornada.';
    agentNodes.offerCanvasPrompt.textContent = brief.canvas_prompt || 'Sem prompt de composição retornado.';
  }

  function renderImages(items) {
    studioState.images = Array.isArray(items) ? items : [];
    if (studioState.images.length) {
      if (studioState.selectedImageIndex < 0 || studioState.selectedImageIndex >= studioState.images.length) {
        studioState.selectedImageIndex = 0;
      }
    } else {
      studioState.selectedImageIndex = -1;
    }

    if (!studioState.images.length) {
      imageGrid.innerHTML = '<p class="marketing-empty">Nenhuma imagem retornada para este tema.</p>';
      return;
    }

    imageGrid.innerHTML = studioState.images.map(function (item, index) {
      const selectedClass = index === studioState.selectedImageIndex ? ' is-selected' : '';
      return ''
        + '<article class="marketing-image-card' + selectedClass + '">'
        + '  <a href="' + escapeHtml(item.source_page || item.image_url || '#') + '" target="_blank" rel="noopener">'
        + '    <img src="' + escapeHtml(item.image_url || '') + '" alt="' + escapeHtml(item.title || 'Imagem relacionada ao tema') + '" loading="lazy" decoding="async">'
        + '  </a>'
        + '  <div class="marketing-image-card__body">'
        + '    <strong>' + escapeHtml(item.title || 'Imagem') + '</strong>'
        + '    <span>' + escapeHtml(item.author || 'Autor não informado') + '</span>'
        + '    <small>' + escapeHtml(item.license || 'Licença não informada') + '</small>'
        + '  </div>'
        + '  <div class="marketing-image-card__actions">'
        + '    <button class="btn ghost marketing-image-card__button" type="button" data-image-index="' + index + '">'
        + (index === studioState.selectedImageIndex ? 'Imagem aplicada' : 'Usar no canvas')
        + '    </button>'
        + '  </div>'
        + '</article>';
    }).join('');
  }

  function rebuildFlyerCanvas() {
    setEditorScene(
      flyerEditor,
      buildFlyerScene(studioState.payload, flyerControlNodes.preset.value, getSelectedImage())
    );
  }

  function rebuildBusinessCardCanvases() {
    setEditorScene(businessFrontEditor, buildBusinessCardScene('front', studioState.payload, getSelectedImage()));
    setEditorScene(businessBackEditor, buildBusinessCardScene('back', studioState.payload, getSelectedImage()));
  }

  function downloadCanvas(canvas, filename) {
    try {
      const link = document.createElement('a');
      link.href = canvas.toDataURL('image/png');
      link.download = filename;
      link.click();
    } catch (error) {
      setStatus('Não foi possível exportar a arte atual. Tente outra imagem ou recarregue a página.', 'error');
    }
  }

  function openPrintWindow(title, html) {
    const printWindow = window.open('', '_blank', 'noopener,noreferrer');
    if (!printWindow) {
      setStatus('O navegador bloqueou a janela de impressão.', 'error');
      return;
    }

    printWindow.document.write(
      '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>' + escapeHtml(title) + '</title>'
      + '<style>'
      + 'body{margin:0;padding:24px;font-family:Inter,system-ui,sans-serif;background:#fff;color:#122033;}'
      + '.print-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;}'
      + '.print-grid img,.print-single img{display:block;width:100%;height:auto;border:1px solid rgba(18,32,51,.12);border-radius:18px;}'
      + '.print-single{max-width:980px;margin:0 auto;}'
      + '@media print{body{padding:0}.print-grid{gap:10px}.print-grid img,.print-single img{border:none;border-radius:0}}'
      + '</style></head><body>' + html
      + '<script>window.onload=function(){window.print();setTimeout(function(){window.close();},200);};<\/script>'
      + '</body></html>'
    );
    printWindow.document.close();
  }

  function printFlyerCanvas() {
    try {
      const src = flyerEditor.canvas.toDataURL('image/png');
      openPrintWindow('Panfleto RPA4ALL', '<div class="print-single"><img src="' + src + '" alt="Panfleto"></div>');
    } catch (error) {
      setStatus('Não foi possível imprimir o panfleto atual.', 'error');
    }
  }

  function printBusinessCards() {
    try {
      const front = businessFrontEditor.canvas.toDataURL('image/png');
      const back = businessBackEditor.canvas.toDataURL('image/png');
      let cards = '';
      for (let index = 0; index < 4; index += 1) {
        cards += '<img src="' + front + '" alt="Frente do cartão">';
        cards += '<img src="' + back + '" alt="Verso do cartão">';
      }
      openPrintWindow('Cartões RPA4ALL', '<div class="print-grid">' + cards + '</div>');
    } catch (error) {
      setStatus('Não foi possível imprimir os cartões atuais.', 'error');
    }
  }

  function applyProfile(profile) {
    profileNodes.name.textContent = profile.name || profile.username || 'Usuário autenticado';
    profileNodes.email.textContent = profile.email || '-';
    profileNodes.username.textContent = profile.username || '-';
    profileNodes.role.textContent = profile.title_hint || 'Especialista RPA4ALL';
    profileNodes.hint.textContent = 'O cartão de visita e o canvas usam a sessão para acelerar o preenchimento.';

    if (!cardFields.name.value) cardFields.name.value = profile.name || profile.username || '';
    if (!cardFields.title.value) cardFields.title.value = profile.title_hint || 'Especialista RPA4ALL';
    if (!cardFields.email.value) cardFields.email.value = profile.email || '';
    if (!cardFields.tagline.value) cardFields.tagline.value = 'Automação inteligente, observabilidade e IA aplicada';
    if (!cardFields.specialties.value) cardFields.specialties.value = 'Storage gerenciado • IA aplicada • observabilidade';
    if (!cardFields.note.value) cardFields.note.value = 'Automação, IA aplicada e observabilidade para operações exigentes.';
    rebuildBusinessCardCanvases();
  }

  function loadProfile() {
    const providers = [sameOriginApiBase + '/marketing/profile'];
    if (developmentFallbackApiBase) {
      providers.push(developmentFallbackApiBase + '/marketing/profile');
    }

    return providers.reduce(function (chain, url) {
      return chain.catch(function () {
        return fetchJson(url, { headers: { Accept: 'application/json' } }).then(function (payload) {
          applyProfile(payload.profile || {});
          return payload;
        });
      });
    }, Promise.reject()).catch(function () {
      profileNodes.name.textContent = 'Perfil indisponível';
      profileNodes.hint.textContent = 'Não foi possível ler a sessão autenticada neste momento.';
    });
  }

  function hydrateStudio(payload) {
    studioState.payload = payload || createFallbackPayload();
    renderBrief(studioState.payload);
    renderAgents(studioState.payload);
    renderImages(((studioState.payload.image_research || {}).items) || []);
    rebuildFlyerCanvas();
    rebuildBusinessCardCanvases();
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const theme = (document.getElementById('marketingTheme').value || '').trim();
    const audience = (document.getElementById('marketingAudience').value || '').trim();
    const notes = (document.getElementById('marketingNotes').value || '').trim();

    if (!theme) {
      setStatus('Informe um tema para gerar o panfleto.', 'error');
      return;
    }

    const providers = [sameOriginApiBase + '/marketing/studio/generate'];
    if (developmentFallbackApiBase) {
      providers.push(developmentFallbackApiBase + '/marketing/studio/generate');
    }

    setStatus('Executando pesquisa, raciocínio comercial e montagem do canvas...', 'pending');

    providers.reduce(function (chain, url) {
      return chain.catch(function () {
        return fetchJson(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: JSON.stringify({ theme: theme, audience: audience, notes: notes })
        }).then(function (payload) {
          hydrateStudio(payload);
          setStatus('Panfleto e canvas gerados com sucesso.', 'success');
          return payload;
        });
      });
    }, Promise.reject()).catch(function () {
      setStatus('Não foi possível gerar o panfleto neste momento.', 'error');
    });
  });

  imageGrid.addEventListener('click', function (event) {
    const button = event.target.closest('[data-image-index]');
    if (!button) {
      return;
    }
    studioState.selectedImageIndex = Number(button.getAttribute('data-image-index'));
    renderImages(studioState.images);
    rebuildFlyerCanvas();
    rebuildBusinessCardCanvases();
  });

  flyerControlNodes.preset.addEventListener('change', function () {
    rebuildFlyerCanvas();
  });

  flyerControlNodes.reset.addEventListener('click', function () {
    rebuildFlyerCanvas();
  });

  flyerControlNodes.download.addEventListener('click', function () {
    downloadCanvas(flyerEditor.canvas, 'rpa4all-flyer.png');
  });

  document.getElementById('marketingFlyerPrint').addEventListener('click', printFlyerCanvas);

  businessControlNodes.downloadFront.addEventListener('click', function () {
    downloadCanvas(businessFrontEditor.canvas, 'rpa4all-card-front.png');
  });

  businessControlNodes.downloadBack.addEventListener('click', function () {
    downloadCanvas(businessBackEditor.canvas, 'rpa4all-card-back.png');
  });

  businessControlNodes.print.addEventListener('click', printBusinessCards);

  Object.values(cardFields).forEach(function (field) {
    field.addEventListener('input', function () {
      rebuildBusinessCardCanvases();
    });
  });

  bindEditorControls(flyerControlNodes, function () {
    return flyerEditor;
  });

  function activeBusinessEditor() {
    return businessControlNodes.side.value === 'back' ? businessBackEditor : businessFrontEditor;
  }

  bindEditorControls(businessControlNodes, activeBusinessEditor);

  businessControlNodes.side.addEventListener('change', function () {
    syncEditorControls(activeBusinessEditor(), businessControlNodes);
  });

  flyerEditor.onSelectionChange = function (editor) {
    syncEditorControls(editor, flyerControlNodes);
  };
  flyerEditor.onSceneChange = function (editor) {
    syncEditorControls(editor, flyerControlNodes);
  };

  businessFrontEditor.onSelectionChange = function () {
    syncEditorControls(activeBusinessEditor(), businessControlNodes);
  };
  businessFrontEditor.onSceneChange = function () {
    syncEditorControls(activeBusinessEditor(), businessControlNodes);
  };
  businessBackEditor.onSelectionChange = function () {
    syncEditorControls(activeBusinessEditor(), businessControlNodes);
  };
  businessBackEditor.onSceneChange = function () {
    syncEditorControls(activeBusinessEditor(), businessControlNodes);
  };

  hydrateStudio(createFallbackPayload());
  loadProfile();
})();
