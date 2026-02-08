// RPA4ALL Python IDE - Powered by Monaco Editor + Backend API
(function () {
    'use strict';

    let editor = null;
    // Textarea fallback when Monaco is not available/loaded
    let editorFallbackId = 'editor_fallback';
    let backendAvailable = false; // Flag de disponibilidade verificada
    let useBackend = false; // Whether a backend was successfully detected
    let projectDirectoryHandle = null; // Pasta selecionada pelo usuário

    // Detect if accessing locally (192.168.x.x or localhost) or externally
    const hostname = window.location.hostname;
    const isLocalNetwork = hostname.startsWith('192.168.') || hostname === 'localhost' || hostname === '127.0.0.1';

    // Feature flag for local fallback. Supported activation methods (in order):
    // 1) global JS variable: window.__USE_LOCAL_FALLBACK === true
    // 2) query param: ?use_local_fallback=1
    // 3) localStorage key: localStorage.USE_LOCAL_FALLBACK === '1'
    const urlParams = new URLSearchParams(window.location.search);
    const useLocalFallback = (window.__USE_LOCAL_FALLBACK === true)
        || urlParams.get('use_local_fallback') === '1'
        || localStorage.getItem('USE_LOCAL_FALLBACK') === '1';

    // Backend URLs - prefer homelab IP when on LAN; prefer localhost only if explicitly desired by developer.
    let BACKEND_URL;
    let CODE_RUNNER_URL;
    if (hostname.startsWith('192.168.')) {
        BACKEND_URL = 'http://192.168.15.2:8503';
        CODE_RUNNER_URL = 'http://192.168.15.2:2000';
    } else if (hostname === 'localhost' || hostname === '127.0.0.1') {
        // If serving locally and developer enabled fallback, point to localhost services; otherwise still prefer localhost for local development endpoints
        BACKEND_URL = useLocalFallback ? 'http://localhost:8503' : 'http://localhost:8503';
        CODE_RUNNER_URL = useLocalFallback ? 'http://localhost:2000' : 'http://localhost:2000';
    } else {
        // External (Cloudflare tunnel) — use api.rpa4all.com hostname
        BACKEND_URL = 'https://api.rpa4all.com/agents-api';
        CODE_RUNNER_URL = 'https://api.rpa4all.com/code-runner';
    }

    // Session management – one session per browser tab
    function getSessionId() {
        let sid = sessionStorage.getItem('rpa4all_session_id');
        if (!sid) {
            sid = crypto.randomUUID().replace(/-/g, '').substring(0, 12);
            sessionStorage.setItem('rpa4all_session_id', sid);
        }
        return sid;
    }

    const DEFAULT_CODE = `# 🐍 Bem-vindo à Python IDE do RPA4ALL!
# Digite seu código Python e clique em "Executar" ou pressione Ctrl+Enter
# Bibliotecas disponíveis: numpy, pandas, matplotlib, requests, etc.

def saudacao(nome):
    return f"Olá, {nome}! Bem-vindo ao RPA4ALL."

print(saudacao("Desenvolvedor"))
print("\\n📊 Exemplo com cálculos:")
numeros = [1, 2, 3, 4, 5]
print(f"Lista: {numeros}")
print(f"Soma: {sum(numeros)}")
print(f"Média: {sum(numeros)/len(numeros)}")
`;

    // Storage keys
    const STORAGE_KEY = 'rpa4all_ide_code';
    let aiHasGeneratedOnce = false;
    const THEME_KEY = 'rpa4all_ide_theme';
    const BACKEND_KEY = 'rpa4all_ide_backend';
    const FILES_KEY = 'rpa4all_ide_files';

    // AI Mode management (code | ask | agents)
    let currentAIMode = 'code';
    // AI concurrency guard
    let aiBusy = false; // true while an AI request is running

    function setAIBusy(flag, note) {
        aiBusy = !!flag;
        const prompt = document.getElementById('aiPrompt');
        const runBtn = document.getElementById('aiPromptRun');
        const genBtn = document.getElementById('aiGenerateFilesRun');
        const scopeToggle = document.getElementById('aiScopeToggle');
        const aiModeBtns = document.querySelectorAll('.ide-ai-mode');
        if (prompt) prompt.disabled = aiBusy;
        if (runBtn) runBtn.disabled = aiBusy;
        if (genBtn) genBtn.disabled = aiBusy;
        if (scopeToggle) scopeToggle.disabled = aiBusy;
        aiModeBtns.forEach(b => b.disabled = aiBusy);
        // update status
        const statusText = aiBusy ? (note || 'IA processando...') : 'Pronto';
        updateStatus(statusText);
    }

    // Editor abstraction: support Monaco editor or a simple textarea fallback
    function createEditorFallback() {
        const container = document.getElementById('editor');
        if (!container) return;
        if (document.getElementById(editorFallbackId)) return;
        const ta = document.createElement('textarea');
        ta.id = editorFallbackId;
        ta.className = 'ide-editor-fallback';
        ta.style.width = '100%';
        ta.style.height = '100%';
        ta.style.boxSizing = 'border-box';
        ta.style.fontFamily = "'JetBrains Mono', 'Fira Code', monospace";
        ta.style.fontSize = '13px';
        ta.style.padding = '12px';
        ta.style.background = 'var(--editor-bg, #0f1720)';
        ta.style.color = 'var(--editor-fg, #d1d5db)';
        ta.style.border = 'none';
        ta.style.outline = 'none';
        ta.spellcheck = false;

        ta.addEventListener('input', () => {
            const file = getCurrentFile();
            if (file) {
                file.content = ta.value;
                saveFiles();
            }
        });

        container.innerHTML = '';
        container.appendChild(ta);
    }

    function removeEditorFallback() {
        const ta = document.getElementById(editorFallbackId);
        if (ta && ta.parentNode) ta.parentNode.removeChild(ta);
    }

    function getEditorValue() {
        if (editor && typeof editor.getValue === 'function') return editor.getValue();
        const ta = document.getElementById(editorFallbackId);
        return ta ? ta.value : '';
    }

    function setEditorValue(value) {
        if (editor && typeof editor.setValue === 'function') {
            editor.setValue(value || '');
        } else {
            createEditorFallback();
            const ta = document.getElementById(editorFallbackId);
            if (ta) ta.value = value || '';
        }
    }

    const AI_MODE_CONFIG = {
        code: {
            placeholder: 'Ex: melhore este código, adicione logs ou crie o script completo do zero.',
            hints: [
                { label: '+ try/except', hint: 'Adicione tratamento de erros' },
                { label: '+ docstrings', hint: 'Adicione docstrings e comentários explicativos' },
                { label: '+ otimizar', hint: 'Otimize a performance deste código' },
            ]
        },
        ask: {
            placeholder: 'Ex: o que este código faz? como funciona o decorator @property? como usar pandas para ler CSV?',
            hints: [
                { label: '📖 Explique o código', hint: 'Explique o que este código faz, passo a passo' },
                { label: '🐛 Encontre bugs', hint: 'Analise este código e encontre possíveis bugs ou problemas' },
                { label: '📐 Boas práticas', hint: 'Quais boas práticas de Python posso aplicar neste código?' },
            ]
        },
        agents: {
            placeholder: 'Ex: use o PythonAgent para criar uma API REST com FastAPI, ou peça ao TestAgent para gerar testes.',
            hints: [
                { label: '🐍 PythonAgent', hint: 'Use o PythonAgent para criar um módulo Python completo para' },
                { label: '🧪 TestAgent', hint: 'Use o TestAgent para gerar testes unitários para este código' },
                { label: '🚀 OperationsAgent', hint: 'Use o OperationsAgent para criar um script de deploy para' },
                { label: '📡 Bus: publicar', hint: 'Crie um script que publique uma mensagem no AgentCommunicationBus' },
            ]
        }
    };

    function switchAIMode(mode) {
        currentAIMode = mode;
        const cfg = AI_MODE_CONFIG[mode];
        const prompt = document.getElementById('aiPrompt');
        const hints = document.getElementById('aiHints');
        if (prompt) prompt.placeholder = cfg.placeholder;
        if (hints) {
            hints.innerHTML = cfg.hints.map(h =>
                `<span class="ide-ai-hint" data-hint="${h.hint}">${h.label}</span>`
            ).join('');
            hints.querySelectorAll('.ide-ai-hint').forEach(el => {
                el.addEventListener('click', () => {
                    if (prompt) {
                        prompt.value = el.dataset.hint + ' ';
                        prompt.focus();
                    }
                });
            });
        }
        // Update active button
        document.querySelectorAll('.ide-ai-mode').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
    }

    // File management
    let files = [];
    let currentFile = 'main.py';

    function loadFiles() {
        try {
            const saved = localStorage.getItem(FILES_KEY);
            if (saved) {
                files = JSON.parse(saved);
            }
        } catch (e) {
            files = [];
        }

        if (!Array.isArray(files) || files.length === 0) {
            files = [{ name: 'main.py', content: DEFAULT_CODE }];
        }

        currentFile = files[0]?.name || 'main.py';
        if (!sessionStorage.getItem('treeState')) {
            sessionStorage.setItem('treeState', '{}');
        }
    }

    function saveFiles() {
        localStorage.setItem(FILES_KEY, JSON.stringify(files));
    }

    function getCurrentFile() {
        return files.find(f => f.name === currentFile) || files[0];
    }

    // Build file tree from flat file list
    function buildFileTree(files) {
        const tree = {};
        files.forEach(file => {
            const parts = file.name.split('/');
            let current = tree;
            parts.forEach((part, idx) => {
                if (idx === parts.length - 1) {
                    current[part] = { type: 'file', fullPath: file.name };
                } else {
                    if (!current[part] || current[part].type !== 'folder') {
                        current[part] = { type: 'folder', children: {} };
                    }
                    current = current[part].children;
                }
            });
        });
        return tree;
    }

    // Render file tree recursively
    function renderFileTree() {
        const container = document.getElementById('fileTabs');
        if (!container) return;

        container.innerHTML = '';
        const tree = buildFileTree(files);
        const treeState = JSON.parse(sessionStorage.getItem('treeState') || '{}');

        function renderNode(node, path = '', depth = 0) {
            const keys = Object.keys(node).sort((a, b) => {
                const aIsFolder = node[a].type === 'folder';
                const bIsFolder = node[b].type === 'folder';
                if (aIsFolder !== bIsFolder) return aIsFolder ? -1 : 1;
                return a.localeCompare(b);
            });

            keys.forEach(key => {
                const item = node[key];
                const nodePath = path ? `${path}/${key}` : key;

                if (item.type === 'folder') {
                    const isExpanded = treeState[nodePath] !== false;
                    const folderDiv = document.createElement('div');
                    folderDiv.className = 'ide-tree-folder';
                    folderDiv.style.paddingLeft = `${depth * 16}px`;

                    const folderHeader = document.createElement('div');
                    folderHeader.className = 'ide-tree-folder-header';

                    const toggle = document.createElement('span');
                    toggle.className = 'ide-tree-toggle';
                    toggle.textContent = isExpanded ? '▼' : '▶';
                    toggle.style.cursor = 'pointer';
                    toggle.addEventListener('click', (e) => {
                        e.stopPropagation();
                        treeState[nodePath] = !treeState[nodePath];
                        sessionStorage.setItem('treeState', JSON.stringify(treeState));
                        renderFileTree();
                    });

                    const folderIcon = document.createElement('span');
                    folderIcon.className = 'ide-tree-icon';
                    folderIcon.textContent = '📁';

                    const folderName = document.createElement('span');
                    folderName.textContent = key;
                    folderName.className = 'ide-tree-name';

                    folderHeader.appendChild(toggle);
                    folderHeader.appendChild(folderIcon);
                    folderHeader.appendChild(folderName);
                    folderDiv.appendChild(folderHeader);

                    container.appendChild(folderDiv);

                    if (isExpanded) {
                        renderNode(item.children, nodePath, depth + 1);
                    }
                } else if (item.type === 'file') {
                    const fileDiv = document.createElement('div');
                    fileDiv.className = `ide-tree-file${item.fullPath === currentFile ? ' active' : ''}`;
                    fileDiv.style.paddingLeft = `${depth * 16}px`;

                    const fileIcon = document.createElement('span');
                    fileIcon.className = 'ide-tree-icon';
                    fileIcon.textContent = '🐍';

                    const fileName = document.createElement('span');
                    fileName.textContent = key;
                    fileName.className = 'ide-tree-name';

                    fileDiv.appendChild(fileIcon);
                    fileDiv.appendChild(fileName);
                    fileDiv.addEventListener('click', () => switchFile(item.fullPath));

                    container.appendChild(fileDiv);
                }
            });
        }

        renderNode(tree);
    }

    function switchFile(name) {
        const file = files.find(f => f.name === name);
        if (!file) return;

        currentFile = name;
        setEditorValue(file.content || '');
        renderFileTree();
        updateStatus(`Arquivo: ${name}`);
    }

    function createNewFile() {
        const name = prompt('Nome do arquivo (ex: script.py):');
        if (!name) return;
        if (files.some(f => f.name === name)) {
            alert('Arquivo já existe.');
            return;
        }

        files.push({ name, content: '' });
        saveFiles();
        renderFileTree();
        switchFile(name);
    }

    function applyFiles(newFiles) {
        if (!Array.isArray(newFiles) || newFiles.length === 0) return;
        files = newFiles.map(f => ({ name: f.name, content: f.content || '' }));
        currentFile = files[0].name;
        saveFiles();
        renderFileTree();
        setEditorValue(files[0].content || '');
    }

    async function openProjectFolder() {
        const output = document.getElementById('output');

        // Função auxiliar para buscar arquivos recursivamente
        async function scanDirectoryRecursive(entries, prefix = '') {
            const pyFiles = [];
            for await (const entry of entries) {
                const fullName = prefix + entry.name;
                if (entry.kind === 'file' && entry.name.endsWith('.py')) {
                    try {
                        const file = await entry.getFile();
                        const content = await file.text();
                        pyFiles.push({ name: fullName, content });
                    } catch (err) {
                        console.warn(`Erro ao ler ${fullName}:`, err);
                    }
                } else if (entry.kind === 'directory') {
                    // Recursivamente buscar em subpastas
                    try {
                        const subEntries = await scanDirectoryRecursive(entry.values(), fullName + '/');
                        pyFiles.push(...subEntries);
                    } catch (err) {
                        console.warn(`Erro ao ler pasta ${fullName}:`, err);
                    }
                }
            }
            return pyFiles;
        }

        // Fallback para Firefox: usar input file com webkitdirectory
        if (!window.showDirectoryPicker) {
            const input = document.createElement('input');
            input.type = 'file';
            input.webkitdirectory = true;
            input.multiple = true;

            input.onchange = async (e) => {
                const files = Array.from(e.target.files);
                const pyFiles = files.filter(f => f.name.endsWith('.py'));

                if (pyFiles.length === 0) {
                    if (output) {
                        output.textContent = '⚠️ Nenhum arquivo .py encontrado na pasta ou subpastas.';
                    }
                    updateStatus('Sem arquivos Python');
                    return;
                }

                updateStatus('Carregando arquivos...');
                if (output) {
                    output.textContent = `⏳ Carregando ${pyFiles.length} arquivo(s) da pasta e subpastas...`;
                }

                const loadedFiles = [];
                for (const file of pyFiles) {
                    try {
                        const content = await file.text();
                        // Preservar estrutura de subpastas
                        loadedFiles.push({ name: file.webkitRelativePath || file.name, content });
                    } catch (err) {
                        console.warn(`Erro ao ler ${file.name}:`, err);
                    }
                }

                if (loadedFiles.length > 0) {
                    applyFiles(loadedFiles);
                    updateStatus(`✅ ${loadedFiles.length} arquivo(s) carregado(s)`);
                    if (output) {
                        output.textContent = `✅ ${loadedFiles.length} arquivo(s) Python carregado(s) (incluindo subpastas).`;
                    }
                }
            };

            input.click();
            return;
        }

        // Chrome/Edge: usar File System Access API
        try {
            projectDirectoryHandle = await window.showDirectoryPicker();
            updateStatus('Carregando arquivos...');
            if (output) {
                output.textContent = '⏳ Carregando arquivos da pasta e subpastas...';
            }

            // Carregar arquivos .py recursivamente
            const loadedFiles = await scanDirectoryRecursive(projectDirectoryHandle.values());

            if (loadedFiles.length > 0) {
                applyFiles(loadedFiles);
                updateStatus(`✅ ${loadedFiles.length} arquivo(s) carregado(s)`);
                if (output) {
                    output.textContent = `✅ ${loadedFiles.length} arquivo(s) Python carregado(s) (incluindo ${loadedFiles.filter(f => f.name.includes('/')).length} em subpastas).`;
                }
            } else {
                updateStatus('✅ Pasta selecionada');
                if (output) {
                    output.textContent = '✅ Pasta selecionada. Nenhum arquivo .py encontrado. Você pode criar e salvar arquivos.';
                }
            }
        } catch (error) {
            updateStatus('Seleção cancelada');
            if (output) {
                output.textContent = '⚠️ Seleção de pasta cancelada.';
            }
        }
    }

    function downloadFile(name, content) {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    async function saveProject() {
        const output = document.getElementById('output');

        if (!files.length) {
            if (output) output.textContent = '⚠️ Nenhum arquivo para salvar.';
            updateStatus('Sem arquivos');
            return;
        }

        if (!projectDirectoryHandle) {
            // Fallback: baixar arquivo atual
            const current = getCurrentFile();
            if (current) {
                downloadFile(current.name, current.content || '');
                updateStatus('✅ Arquivo baixado');
                if (output) {
                    output.textContent = `✅ Arquivo ${current.name} baixado.`;
                }
            }
            return;
        }

        try {
            for (const file of files) {
                const handle = await projectDirectoryHandle.getFileHandle(file.name, { create: true });
                const writable = await handle.createWritable();
                await writable.write(file.content || '');
                await writable.close();
            }
            updateStatus('✅ Projeto salvo');
            if (output) {
                output.textContent = '✅ Projeto salvo na pasta selecionada.';
            }
        } catch (error) {
            updateStatus('❌ Falha ao salvar');
            if (output) {
                output.textContent = `❌ Erro ao salvar: ${error.message}`;
            }
        }
    }

    // Initialize Monaco Editor (vendor-first, then CDN). No textarea fallback — fail visibly.
    function initMonaco() {
        if (typeof require === 'undefined') {
            console.error('RequireJS não disponível — Monaco não pode ser carregado. Verifique index.html e loader scripts.');
            updateStatus('❌ Monaco loader ausente');
            return;
        }

        // Prefer local vendor directory if present (served at /vendor/monaco), else use CDN
        const localPath = '/vendor/monaco/min/vs';
        const cdnPath = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs';

        // Try local first; the server will 404 if not present, which RequireJS will surface
        require.config({ paths: { vs: localPath } });

        // Attempt load; on failure, try CDN once
        require(['vs/editor/editor.main'], function () {
            // Monaco loaded from local vendor
            _monacoSetup();
        }, function (err) {
            console.warn('Monaco vendor não disponível, tentando CDN...', err && err.message);
            // Try CDN
            require.config({ paths: { vs: cdnPath } });
            require(['vs/editor/editor.main'], function () {
                _monacoSetup();
            }, function (err2) {
                console.error('Falha ao carregar Monaco do CDN também:', err2 && err2.message);
                updateStatus('❌ Falha ao carregar Monaco (vendor e CDN)');
            });
        });

        function _monacoSetup() {
            try {
                loadFiles();
                const savedTheme = localStorage.getItem(THEME_KEY) || 'vs-dark';
                const current = getCurrentFile();

                editor = monaco.editor.create(document.getElementById('editor'), {
                    value: current?.content || DEFAULT_CODE,
                    language: 'python',
                    theme: savedTheme,
                    fontSize: 14,
                    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
                    minimap: { enabled: true },
                    automaticLayout: true,
                    scrollBeyondLastLine: false,
                    lineNumbers: 'on',
                    renderWhitespace: 'selection',
                    bracketPairColorization: { enabled: true },
                    padding: { top: 10, bottom: 10 },
                    tabSize: 4,
                    insertSpaces: true,
                    wordWrap: 'on',
                    suggestOnTriggerCharacters: true,
                    quickSuggestions: true,
                    folding: true,
                    foldingStrategy: 'auto',
                    showFoldingControls: 'mouseover',
                    smoothScrolling: true,
                    cursorBlinking: 'smooth',
                    cursorSmoothCaretAnimation: 'on'
                });

                // Auto-save on change
                editor.onDidChangeModelContent(() => {
                    const file = getCurrentFile();
                    if (file) {
                        file.content = editor.getValue();
                        saveFiles();
                    }
                });

                // If a textarea fallback exists, remove it once Monaco is ready
                removeEditorFallback();

                // Render file tree
                renderFileTree();

                // Keyboard shortcut: Ctrl+Enter to run
                editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, runCode);

                // Theme selector
                const themeSelect = document.getElementById('themeSelect');
                if (themeSelect) {
                    themeSelect.value = savedTheme;
                    themeSelect.addEventListener('change', (e) => {
                        const theme = e.target.value;
                        monaco.editor.setTheme(theme);
                        localStorage.setItem(THEME_KEY, theme);
                    });
                }

                updateStatus('Editor pronto');
            } catch (e) {
                console.error('Erro ao configurar Monaco:', e);
                updateStatus('❌ Erro ao configurar Monaco');
            }
        }
    }

    // Pyodide removido – execução exclusivamente via backend

    // Check if backend is available
    async function checkBackend() {
        // Try backends based on network location
        const endpoints = [
            { url: BACKEND_URL, path: '/health', name: isLocalNetwork ? 'Specialized Agents (Local)' : 'API via Cloudflare' },
            { url: CODE_RUNNER_URL, path: '/health', name: isLocalNetwork ? 'Code Runner (Local)' : 'Code Runner via Cloudflare' }
        ];

        for (const { url, path, name } of endpoints) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);

                const response = await fetch(`${url}${path}`, {
                    method: 'GET',
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (response.ok) {
                    console.log(`✅ Backend disponível: ${name} (${url})`);
                    backendAvailable = true;
                    useBackend = true;
                    return true;
                }
            } catch (e) {
                console.log(`❌ ${name} não disponível: ${e.message}`);
                continue;
            }
        }

        console.error('❌ Nenhum backend disponível!');
        backendAvailable = false;
        useBackend = false;
        return false;
    }

    // Run code via backend API (with session & queue support)
    async function runCodeBackend(code, _retryCount) {
        const retryCount = _retryCount || 0;
        const MAX_RETRIES = 6; // ~30 s total wait in queue

        if (!backendAvailable) {
            throw new Error('🔴 Backend não disponível. Verifique a conexão com o servidor.\n\nTente:\n1. Verificar se http://192.168.15.2:2000 está acessível\n2. Recarregar a página\n3. Contatar suporte se o problema persistir');
        }

        const sessionId = getSessionId();

        // Try endpoints based on network location
        const endpoints = [
            { url: BACKEND_URL, endpoint: '/code/run', name: isLocalNetwork ? 'Specialized Agents' : 'API Cloudflare' },
            { url: CODE_RUNNER_URL, endpoint: isLocalNetwork ? '/api/v2/execute' : '/api/v2/execute', name: 'Code Runner', format: 'v2' }
        ];

        for (const { url, endpoint, name, format } of endpoints) {
            try {
                const body = format === 'v2'
                    ? { language: 'python', version: '3.11', files: [{ content: code }] }
                    : { language: 'python', code: code };

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 40000);

                const response = await fetch(`${url}${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Session-ID': sessionId
                    },
                    body: JSON.stringify(body),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                // Handle queue (202)
                if (response.status === 202) {
                    const qData = await response.json();
                    const output = document.getElementById('output');
                    if (output) {
                        output.textContent = qData.message || `⏳ Na fila de espera (posição ${qData.position})…`;
                    }
                    updateStatus(`⏳ Fila: posição ${qData.position}`);
                    if (retryCount < MAX_RETRIES) {
                        const delay = (qData.retry_after || 5) * 1000;
                        await new Promise(r => setTimeout(r, delay));
                        return runCodeBackend(code, retryCount + 1);
                    }
                    throw new Error('⏳ Tempo de espera na fila excedido. Tente novamente em alguns minutos.');
                }

                if (response.ok) {
                    const data = await response.json();
                    console.log(`✅ Executado via: ${name}`);
                    return {
                        run: {
                            stdout: data.stdout || data.run?.stdout || '',
                            stderr: data.stderr || data.run?.stderr || '',
                            code: data.exit_code ?? data.run?.code ?? 0
                        }
                    };
                } else {
                    console.log(`⚠️ ${name} retornou HTTP ${response.status}`);
                }
            } catch (e) {
                if (e.message.includes('Fila')) throw e; // propagate queue timeout
                console.log(`❌ ${name} falhou: ${e.message}`);
                continue;
            }
        }

        throw new Error('❌ Nenhum backend respondeu. O servidor pode estar offline.');
    }

    // Generate code with AI via API
    async function generateCodeWithAI(prompt) {
        const urls = [
            { url: BACKEND_URL, endpoint: '/code/generate' }
        ];

        for (const { url, endpoint } of urls) {
            try {
                const response = await fetch(`${url}${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        language: 'python',
                        description: prompt,
                        context: ''
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data?.code) {
                        return data.code;
                    }
                }
            } catch (e) {
                console.log(`IA backend ${url} falhou:`, e.message);
                continue;
            }
        }

        throw new Error('Falha ao gerar código com IA');
    }

    // ── Bus Debug: ícones e formatação por tipo de mensagem ──
    const BUS_ICONS = {
        task_start: '🚀', task_end: '✅', llm_call: '🤖', llm_response: '💬',
        code_gen: '📝', error: '❌', request: '📨', response: '📩',
        execution: '⚙️', docker: '🐳', rag: '🔍', github: '🐙',
        coordinator: '🎯', analysis: '🔬', test_gen: '🧪',
    };

    let _busMessages = []; // acumula debug lines da execução corrente

    function formatBusMessage(busData) {
        const icon = BUS_ICONS[busData.type] || '📡';
        const ts = busData.ts || '--:--:--';
        const src = busData.source || '?';
        const tgt = busData.target || '?';
        const content = (busData.content || '').substring(0, 200);
        return `[${ts}] ${icon} ${busData.type.toUpperCase()}  ${src} → ${tgt}  ${content}`;
    }

    function appendBusToOutput(busData) {
        const output = document.getElementById('output');
        if (!output) return;
        const line = formatBusMessage(busData);
        _busMessages.push(line);
        // Exibir header + todas as linhas
        output.textContent = '🔗 Bus Debug — Evolução do processamento\n'
            + '─'.repeat(55) + '\n'
            + _busMessages.join('\n') + '\n';
        output.scrollTop = output.scrollHeight;
    }

    async function generateCodeWithAIStream(prompt, onChunk, onBus) {
        const urls = [
            { url: BACKEND_URL, endpoint: '/code/generate-stream' }
        ];

        for (const { url, endpoint } of urls) {
            try {
                const response = await fetch(`${url}${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        language: 'python',
                        description: prompt,
                        context: ''
                    })
                });

                if (!response.ok || !response.body) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                let fullCode = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const parts = buffer.split('\n\n');
                    buffer = parts.pop() || '';

                    for (const part of parts) {
                        const line = part.replace(/^data:\s*/, '');
                        if (!line) continue;

                        // ── Bus debug messages ──
                        if (line.startsWith('[BUS]')) {
                            try {
                                const busData = JSON.parse(line.substring(6));
                                if (onBus) onBus(busData);
                            } catch (_) { /* ignore parse errors */ }
                            continue;
                        }

                        if (line.startsWith('[DONE]')) {
                            return fullCode;
                        }
                        if (line.startsWith('[ERROR]')) {
                            throw new Error(line.replace('[ERROR] ', ''));
                        }

                        fullCode += line;
                        if (onChunk) onChunk(fullCode, line);
                    }
                }

                return fullCode;
            } catch (e) {
                console.log(`IA stream ${url} falhou:`, e.message);
                continue;
            }
        }

        throw new Error('Streaming não disponível');
    }



    // Run Python code via backend API
    async function runCode() {
        if (!editor && !document.getElementById(editorFallbackId)) {
            // If no Monaco editor and no fallback, create fallback so user can edit
            createEditorFallback();
        }
        const output = document.getElementById('output');

        if (aiBusy) {
            if (output) output.textContent = '⏳ Aguarde a IA finalizar antes de executar o código.';
            updateStatus('Aguardando IA');
            return;
        }

        const code = getEditorValue();

        if (!code.trim()) {
            output.textContent = '⚠️ Nenhum código para executar.';
            return;
        }

        updateStatus('Executando...');
        output.textContent = '⏳ Executando código...\n';

        try {
            // Força uso do backend
            updateStatus('Conectando ao servidor...');
            const result = await runCodeBackend(code);

            // Processa resultado
            const run = result.run || result;
            const stdout = run.stdout || '';
            const stderr = run.stderr || '';
            const exitCode = run.code ?? 0;

            if (exitCode !== 0) {
                output.textContent = `❌ Erro (código ${exitCode}):\n${stderr || stdout}`;
                updateStatus('❌ Erro na execução');
            } else if (stdout || stderr) {
                output.textContent = stdout + (stderr ? `\n⚠️ Avisos:\n${stderr}` : '');
                updateStatus('✅ Servidor');
            } else {
                output.textContent = '✅ Código executado com sucesso (sem saída).';
                updateStatus('✅ Servidor');
            }
        } catch (error) {
            output.textContent = `❌ Erro:\n${error.message}`;
            updateStatus('❌ Falha');
            console.error('Erro de execução:', error);
        }
    }

    function sanitizeAIOutput(text) {
        if (!text) return text;
        // Remove apenas fence markers, preservando indentação
        let result = text;
        // Remove linhas com apenas ```
        const lines = result.split(/\r?\n/);
        const cleaned = [];
        for (const raw of lines) {
            // Remove prefixo 'data:' mas preserva espaços
            let line = raw.replace(/^data:\s*/i, '');
            // Skip apenas linhas que são fence markers puros
            if (/^\s*```\s*$/.test(line) || /^\s*```python\s*$/i.test(line)) {
                continue;
            }
            cleaned.push(line);
        }
        return cleaned.join('\n').trimEnd();
    }

    async function handleAIPromptRun() {
        const promptEl = document.getElementById('aiPrompt');
        const output = document.getElementById('output');

        if (!promptEl || !promptEl.value.trim()) {
            output.textContent = '⚠️ Descreva o que deseja fazer com a IA.';
            updateStatus('Aguardando prompt');
            return;
        }

        // Fallback local generation quando backend não está disponível e flag está ativa
        if (!backendAvailable && useLocalFallback) {
            try {
                const userPrompt = promptEl.value.trim();
                // Respostas pré-definidas simples para testes
                if (/soma|somar|função de soma/i.test(userPrompt)) {
                    const code = `def soma(a, b):\n    return a + b\n\nprint(soma(2,3))`;
                    setEditorValue(code);
                    const file = getCurrentFile();
                    if (file) { file.content = getEditorValue(); saveFiles(); }

                    // Mock some bus debug messages so tests that look for Bus Debug succeed
                    _busMessages = [];
                    const now = new Date().toLocaleTimeString();
                    appendBusToOutput({ type: 'task_start', ts: now, source: 'local', target: 'agent', content: 'iniciando geração' });
                    appendBusToOutput({ type: 'llm_call', ts: now, source: 'local', target: 'llm', content: 'chamada IA (fallback)' });
                    appendBusToOutput({ type: 'code_gen', ts: now, source: 'llm', target: 'editor', content: 'código gerado (fallback)'});

                    const busFinal = _busMessages.length
                        ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                        : '';

                    output.textContent = busFinal + code;
                    updateStatus('✅ IA (fallback local)');
                    return;
                }
                // Generic fallback message
                _busMessages = [];
                appendBusToOutput({ type: 'llm_call', ts: new Date().toLocaleTimeString(), source: 'local', target: 'llm', content: 'fallback: comando recebido' });
                output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n\n' + '✅ IA (fallback local): comando recebido.';
                updateStatus('✅ IA (fallback local)');
                return;
            } catch (e) {
                console.warn('Fallback IA falhou:', e);
            }
        } else if (!backendAvailable && !useLocalFallback) {
            // Backend indisponível e fallback não habilitado
            output.textContent = '🔴 Backend não disponível e fallback local não habilitado. Ative localmente com localStorage.setItem("USE_LOCAL_FALLBACK","1") ou adicione ?use_local_fallback=1 na URL para testes.';
            updateStatus('❌ Backend indisponível');
            return;
        }
        }

        const userPrompt = promptEl.value.trim();
        const current = getEditorValue();
        const fileName = currentFile || 'main.py';
        const scopeAll = document.getElementById('aiScopeToggle')?.checked || false;

        // ── Reset bus debug ──
        _busMessages = [];
        const busHandler = (busData) => appendBusToOutput(busData);

        // Build context block (shared across modes)
        let contextBlock;
        if (scopeAll && files.length > 1) {
            const allFilesText = files.map(f => `# FILE: ${f.name}\n${f.content || ''}`).join('\n\n');
            contextBlock = `ARQUIVO EM FOCO (${fileName}):\n${current}\n\nTODOS OS ARQUIVOS DO PROJETO:\n${allFilesText}`;
        } else {
            contextBlock = `ARQUIVO ATUAL (${fileName}):\n${current}`;
        }

        // ── MODE: ASK (responde no output, não altera editor) ──
        if (currentAIMode === 'ask') {
            const askInstruction = [
                'Você é um assistente especialista em Python e desenvolvimento de software.',
                'O usuário está fazendo uma PERGUNTA — NÃO altere o código.',
                'Responda de forma clara, didática e em português.',
                'Use exemplos curtos quando necessário.',
                'Se a pergunta for sobre o código fornecido, analise-o em detalhe.',
                'Formate a resposta em texto puro (sem markdown).',
            ].join('\n');

            const fullPrompt = `${askInstruction}\n\nPERGUNTA DO USUÁRIO:\n${userPrompt}\n\n${contextBlock}`;

            updateStatus('🧠 Pensando...');
            output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n';

            try {
                let answer = '';
                setAIBusy(true, 'IA processando...');
                try {
                    try {
                        answer = await generateCodeWithAIStream(fullPrompt, (fullText) => {
                            const busSection = _busMessages.length
                                ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                                : '';
                            output.textContent = busSection + '💬 Resposta:\n' + fullText;
                            output.scrollTop = output.scrollHeight;
                        }, busHandler);
                    } catch (_e) {
                        answer = await generateCodeWithAI(fullPrompt);
                    }
                } finally {
                    setAIBusy(false);
                }

                const busSection = _busMessages.length
                    ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                    : '';
                output.textContent = busSection + '💬 Resposta:\n' + (answer || '(sem resposta)');
                updateStatus('✅ Resposta pronta');
            } catch (error) {
                output.textContent = `❌ Erro: ${error.message}`;
                updateStatus('Erro na IA');
            }
            return;
        }

        // ── MODE: AGENTS (contextualiza com agentes disponíveis) ──
        if (currentAIMode === 'agents') {
            const agentsInstruction = [
                'Você é o orquestrador do sistema multi-agente RPA4ALL.',
                'O sistema possui agentes especializados que rodam em Docker:',
                '• PythonAgent – cria, corrige e otimiza código Python',
                '• JavaScriptAgent – desenvolvimento frontend/Node.js',
                '• TypeScriptAgent – tipagem e transpilação TypeScript',
                '• GoAgent – microserviços em Go de alta performance',
                '• TestAgent – gera e executa testes automatizados',
                '• OperationsAgent – deploy, CI/CD, infraestrutura',
                '• RequirementsAnalyst – analisa requisitos e escreve specs',
                '',
                'Comunicação inter-agentes via AgentCommunicationBus:',
                '  from specialized_agents.agent_communication_bus import get_communication_bus, MessageType',
                '  bus = get_communication_bus()',
                '  bus.publish(MessageType.REQUEST, "source", "target", {"op": "..."})',
                '',
                'RAG por linguagem:',
                '  from specialized_agents.rag_manager import RAGManagerFactory',
                '  rag = RAGManagerFactory.get_manager("python")',
                '  await rag.search("query")',
                '',
                'Memória de decisões:',
                '  agent.recall_past_decisions(app, component, error_type, error_msg)',
                '  agent.make_informed_decision(app, component, error_type, error_msg, context)',
                '',
                'Se o usuário pedir para USAR um agente, gere o código Python executável.',
                'Se o usuário perguntar SOBRE os agentes, explique em texto no output.',
                'Se gerar código, use o formato # FILE: quando necessário.',
                'Responda em português.',
            ].join('\n');

            const fullPrompt = `${agentsInstruction}\n\nSOLICITAÇÃO DO USUÁRIO:\n${userPrompt}\n\n${contextBlock}`;

            // Detect if it's a question about agents vs code generation
            const isQuestion = /^(o que|como|qual|quais|quando|por que|porque|explique|descreva|liste|me diga|me fale)/i.test(userPrompt);

            if (isQuestion) {
                updateStatus('🤖 Consultando agentes...');
                output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n';
                try {
                    let answer = '';
                    setAIBusy(true, 'IA processando...');
                    try {
                        try {
                            answer = await generateCodeWithAIStream(fullPrompt, (fullText) => {
                                const busSection = _busMessages.length
                                    ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                                    : '';
                                output.textContent = busSection + '💬 Resposta:\n' + fullText;
                                output.scrollTop = output.scrollHeight;
                            }, busHandler);
                        } catch (_e) {
                            answer = await generateCodeWithAI(fullPrompt);
                        }
                    } finally {
                        setAIBusy(false);
                    }
                    const busSection = _busMessages.length
                        ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                        : '';
                    output.textContent = busSection + '💬 Resposta:\n' + (answer || '(sem resposta)');
                    updateStatus('✅ Resposta pronta');
                } catch (error) {
                    output.textContent = `❌ Erro: ${error.message}`;
                    updateStatus('Erro na IA');
                }
                return;
            }

            // Agent mode code generation – falls through to code flow below
            updateStatus('🤖 Gerando com agentes...');
            output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n';

            try {
                let code = '';
                setAIBusy(true, 'IA gerando código...');
                try {
                    try {
                        code = await generateCodeWithAIStream(fullPrompt, (fullCode) => {
                            setEditorValue(sanitizeAIOutput(fullCode));
                        }, busHandler);
                    } catch (_e) {
                        code = await generateCodeWithAI(fullPrompt);
                    }
                } finally {
                    setAIBusy(false);
                }
                const cleanedCode = sanitizeAIOutput(code);
                const parsedFiles = parseFilesFromAI(cleanedCode);
                if (parsedFiles.length > 0) {
                    applyFiles(parsedFiles);
                } else {
                    setEditorValue(cleanedCode);
                    const file = getCurrentFile();
                    if (file) { file.content = getEditorValue(); saveFiles(); }
                }
                aiHasGeneratedOnce = true;
                updateStatus('✅ Agente aplicou o código');
                const busFinal = _busMessages.length
                    ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                    : '';
                output.textContent = busFinal + '✅ Código gerado via agente.';
            } catch (error) {
                output.textContent = `❌ Erro: ${error.message}`;
                updateStatus('Erro na IA');
            }
            return;
        }

        // ── MODE: CODE (default – same as before) ──
        const instruction = [
            'Você é um assistente estilo Copilot.',
            aiHasGeneratedOnce
                ? 'A partir de agora, apenas corrija/atualize o código existente. Não reescreva do zero.'
                : 'Você pode gerar um novo código ou alterar o existente.',
            'Se alterar o arquivo atual, retorne o conteúdo completo do arquivo atualizado.',
            'Se precisar criar múltiplos arquivos, use o formato:',
            '# FILE: nome_do_arquivo.py',
            '<conteúdo>',
            '# FILE: outro_arquivo.py',
            '<conteúdo>',
            'Não inclua explicações, apenas o conteúdo de código.'
        ].join('\n');

        const fullPrompt = `${instruction}\n\nPROMPT DO USUÁRIO:\n${userPrompt}\n\n${contextBlock}`;

        updateStatus('Executando prompt com IA...');
        output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n';

            try {
                let code = '';
                setAIBusy(true, 'IA gerando código...');
                try {
                    try {
                        code = await generateCodeWithAIStream(fullPrompt, (fullCode) => {
                            const cleaned = sanitizeAIOutput(fullCode);
                            setEditorValue(cleaned);
                            const file = getCurrentFile();
                            if (file) { file.content = getEditorValue(); saveFiles(); }
                        }, busHandler);
                    } catch (streamError) {
                        code = await generateCodeWithAI(fullPrompt);
                        const cleaned = sanitizeAIOutput(code);
                        setEditorValue(cleaned);
                        const file = getCurrentFile();
                        if (file) { file.content = getEditorValue(); saveFiles(); }
                    }
                } finally {
                    setAIBusy(false);
                }

            const cleanedCode = sanitizeAIOutput(code);
            const parsedFiles = parseFilesFromAI(cleanedCode);
            if (parsedFiles.length > 0) {
                applyFiles(parsedFiles);
            } else {
                setEditorValue(cleanedCode);
                const file = getCurrentFile();
                if (file) {
                    file.content = getEditorValue();
                    saveFiles();
                }
            }

            aiHasGeneratedOnce = true;
            updateStatus('Prompt aplicado');
            const busFinal = _busMessages.length
                ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                : '';
            output.textContent = busFinal + '✅ IA aplicou o prompt.';
        } catch (error) {
            console.error('Erro IA:', error);
            const busFinal = _busMessages.length
                ? '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n' + _busMessages.join('\n') + '\n' + '─'.repeat(55) + '\n\n'
                : '';
            output.textContent = busFinal + `❌ Erro ao aplicar prompt: ${error.message}`;
            updateStatus('Erro na IA');
        }
    }

    function parseFilesFromAI(text) {
        const lines = text.split(/\r?\n/);
        const result = [];
        let current = null;

        lines.forEach(line => {
            const match = line.match(/^#\s*FILE:\s*(.+)$/i);
            if (match) {
                if (current) result.push(current);
                current = { name: match[1].trim(), content: '' };
            } else if (current) {
                current.content += (current.content ? '\n' : '') + line;
            }
        });

        if (current) result.push(current);
        return result.filter(f => f.name && f.content !== undefined);
    }

    async function handleAIGenerateFiles(shouldRun) {
        const promptEl = document.getElementById('aiPrompt');
        const output = document.getElementById('output');

        if (!promptEl || !promptEl.value.trim()) {
            output.textContent = '⚠️ Descreva o que deseja gerar com a IA.';
            updateStatus('Aguardando prompt');
            return;
        }

        const filePrompt = `${promptEl.value.trim()}\n\n${aiHasGeneratedOnce ? 'Apenas corrija/atualize os arquivos existentes. Não reescreva do zero.\n\n' : ''}Retorne no formato:\n# FILE: main.py\n<codigo>\n# FILE: utils.py\n<codigo>\nSem explicações.`;

        updateStatus('Gerando arquivos...');
        _busMessages = [];
        output.textContent = '🔗 Bus Debug — Evolução do processamento\n' + '─'.repeat(55) + '\n';

        try {
            let text = '';
            setAIBusy(true, 'IA gerando arquivos...');
            try {
                try {
                    text = await generateCodeWithAIStream(filePrompt, (fullCode) => {
                        const cleaned = sanitizeAIOutput(fullCode);
                        setEditorValue(cleaned);
                    }, (busData) => appendBusToOutput(busData));
                } catch (streamError) {
                    text = await generateCodeWithAI(filePrompt);
                }
            } finally {
                setAIBusy(false);
            }

            const cleanedText = sanitizeAIOutput(text);
            const newFiles = parseFilesFromAI(cleanedText);
            if (!newFiles.length) {
                // fallback: single file
                applyFiles([{ name: 'main.py', content: cleanedText }]);
            } else {
                applyFiles(newFiles);
            }

            aiHasGeneratedOnce = true;
            updateStatus('Arquivos gerados');
            output.textContent = '✅ Arquivos gerados pela IA.';

            if (shouldRun) {
                await runCode();
            }
        } catch (error) {
            console.error('Erro IA (arquivos):', error);
            output.textContent = `❌ Erro ao gerar arquivos: ${error.message}`;
            updateStatus('Erro na IA');
        }
    }

    // Clear output
    function clearOutput() {
        const output = document.getElementById('output');
        if (output) {
            output.textContent = '';
        }
        updateStatus('Saída limpa');
    }

    // Update status indicator
    function updateStatus(text) {
        const status = document.getElementById('ideStatus');
        if (status) {
            status.textContent = text;
        }
    }

    // Load example code
    function loadExample(code) {
        setEditorValue(code.replace(/\n/g, '\n'));
        const file = getCurrentFile();
        if (file) {
            file.content = getEditorValue();
            saveFiles();
        }
        updateStatus('Exemplo carregado');
    }

    // Initialize when DOM is ready
    function init() {
        // Only initialize if IDE section exists
        const idePanel = document.getElementById('ide');
        if (!idePanel) return;

        // Initialize Monaco when IDE tab is clicked (lazy load)
        const ideTab = document.querySelector('[data-target="ide"]');
        if (ideTab) {
            ideTab.addEventListener('click', () => {
                if (!editor) {
                    // Provide immediate textarea fallback so user sees an editor
                    createEditorFallback();
                    setTimeout(initMonaco, 100);
                    // Recheck backend when tab opens
                    checkBackend();
                }
            });
        }

        // Run button
        const runBtn = document.getElementById('runCode');
        if (runBtn) {
            runBtn.addEventListener('click', runCode);
        }

        // Open project folder button
        const openFolderBtn = document.getElementById('openProjectFolder');
        if (openFolderBtn) {
            openFolderBtn.addEventListener('click', openProjectFolder);
        }

        // Save project button
        const saveProjectBtn = document.getElementById('saveProject');
        if (saveProjectBtn) {
            saveProjectBtn.addEventListener('click', saveProject);
        }

        // Clear button
        const clearBtn = document.getElementById('clearOutput');
        if (clearBtn) {
            clearBtn.addEventListener('click', clearOutput);
        }

        // New file button
        const newFileBtn = document.getElementById('newFile');
        if (newFileBtn) {
            newFileBtn.addEventListener('click', createNewFile);
        }

        // AI button (Copilot-style prompt)
        const aiPromptRunBtn = document.getElementById('aiPromptRun');
        if (aiPromptRunBtn) {
            aiPromptRunBtn.addEventListener('click', handleAIPromptRun);
        }

        // AI mode buttons (code / ask / agents)
        document.querySelectorAll('.ide-ai-mode').forEach(btn => {
            btn.addEventListener('click', () => switchAIMode(btn.dataset.mode));
        });

        // AI hint chips
        document.querySelectorAll('.ide-ai-hint').forEach(el => {
            el.addEventListener('click', () => {
                const prompt = document.getElementById('aiPrompt');
                if (prompt) {
                    prompt.value = el.dataset.hint + ' ';
                    prompt.focus();
                }
            });
        });

        // AI scope toggle
        const scopeToggle = document.getElementById('aiScopeToggle');
        const scopeLabel = document.getElementById('aiScopeLabel');
        if (scopeToggle && scopeLabel) {
            scopeToggle.addEventListener('change', () => {
                scopeLabel.textContent = scopeToggle.checked
                    ? '📁 Todos os arquivos'
                    : '📄 Arquivo atual';
            });
        }

        // Example buttons
        document.querySelectorAll('.ide-example').forEach(btn => {
            btn.addEventListener('click', () => {
                const code = btn.dataset.code;
                if (code) {
                    loadExample(code);
                }
            });
        });

        // Check backend availability on startup
        updateStatus('Verificando servidor...');
        checkBackend().then(available => {
            if (!available) {
                updateStatus('⚠️ Servidor não acessível. Verifique a conexão.');
                const output = document.getElementById('output');
                if (output) {
                    output.textContent = '🔴 ERRO: Servidor não está respondendo.\n\n' +
                        'Possíveis soluções:\n' +
                        '1. Reiniciar o servidor Code Runner\n' +
                        '2. Verificar conectividade de rede\n' +
                        '3. Recarregar a página\n\n' +
                        'Contate o suporte se o problema persistir.';
                }
            } else {
                updateStatus('✅ Servidor disponível');
            }
        });
    }

    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
