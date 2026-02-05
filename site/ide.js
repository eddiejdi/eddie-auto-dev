// RPA4ALL Python IDE - Powered by Monaco Editor + Backend/Pyodide
(function () {
    'use strict';

    let editor = null;
    let pyodide = null;
    let isLoading = false;
    let useBackend = true; // Preferir backend quando disponível
    let backendAvailable = false; // Flag de disponibilidade verificada
    let projectDirectoryHandle = null; // Pasta selecionada pelo usuário

    // Backend Code Runner API
    const BACKEND_URL = 'https://api.rpa4all.com'; // API pública via Cloudflare
    const BACKEND_FALLBACK = 'http://192.168.15.2:8503'; // API local direta
    const CODE_RUNNER_DIRECT = 'http://192.168.15.2:2000'; // Code Runner direto

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
    const THEME_KEY = 'rpa4all_ide_theme';
    const BACKEND_KEY = 'rpa4all_ide_backend';
    const FILES_KEY = 'rpa4all_ide_files';

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
    }

    function saveFiles() {
        localStorage.setItem(FILES_KEY, JSON.stringify(files));
    }

    function getCurrentFile() {
        return files.find(f => f.name === currentFile) || files[0];
    }

    function renderFileTabs() {
        const container = document.getElementById('fileTabs');
        if (!container) return;

        container.innerHTML = '';
        files.forEach(file => {
            const tab = document.createElement('span');
            tab.className = `ide-file-tab${file.name === currentFile ? ' active' : ''}`;
            tab.textContent = file.name;
            tab.addEventListener('click', () => switchFile(file.name));
            container.appendChild(tab);
        });
    }

    function switchFile(name) {
        const file = files.find(f => f.name === name);
        if (!file || !editor) return;

        currentFile = name;
        editor.setValue(file.content || '');
        renderFileTabs();
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
        renderFileTabs();
        switchFile(name);
    }

    function applyFiles(newFiles) {
        if (!Array.isArray(newFiles) || newFiles.length === 0) return;
        files = newFiles.map(f => ({ name: f.name, content: f.content || '' }));
        currentFile = files[0].name;
        saveFiles();
        renderFileTabs();
        if (editor) {
            editor.setValue(files[0].content || '');
        }
    }

    async function openProjectFolder() {
        const output = document.getElementById('output');
        if (!window.showDirectoryPicker) {
            if (output) {
                output.textContent = '⚠️ Seu navegador não suporta acesso a pastas. Use Chrome/Edge.';
            }
            updateStatus('Sem suporte a pasta');
            return;
        }

        try {
            projectDirectoryHandle = await window.showDirectoryPicker();
            updateStatus('✅ Pasta selecionada');
            if (output) {
                output.textContent = '✅ Pasta do projeto selecionada. Você pode salvar os arquivos.';
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

    // Initialize Monaco Editor
    function initMonaco() {
        require.config({
            paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }
        });

        require(['vs/editor/editor.main'], function () {
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

            // Render file tabs
            renderFileTabs();

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
        });
    }

    // Initialize Pyodide
    async function initPyodide() {
        if (pyodide) return pyodide;
        if (isLoading) return null;

        isLoading = true;
        updateStatus('Carregando Python local...');

        try {
            pyodide = await loadPyodide({
                indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/'
            });

            // Pre-load common packages
            updateStatus('Carregando bibliotecas...');
            await pyodide.loadPackage(['numpy', 'pandas']);

            updateStatus('Pronto (local)');
            isLoading = false;
            return pyodide;
        } catch (error) {
            console.error('Erro ao carregar Pyodide:', error);
            updateStatus('Erro ao carregar Python local');
            isLoading = false;
            return null;
        }
    }

    // Check if backend is available
    async function checkBackend() {
        // Try em ordem: API pública > API local > Code Runner direto
        const endpoints = [
            { url: BACKEND_URL, path: '/health', name: 'API Pública' },
            { url: BACKEND_FALLBACK, path: '/health', name: 'API Local' },
            { url: CODE_RUNNER_DIRECT, path: '/health', name: 'Code Runner' }
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

    // Run code via backend API
    async function runCodeBackend(code) {
        if (!backendAvailable) {
            throw new Error('🔴 Backend não disponível. Verifique a conexão com o servidor.\n\nTente:\n1. Verificar se http://192.168.15.2:2000 está acessível\n2. Recarregar a página\n3. Contatar suporte se o problema persistir');
        }

        // Try endpoints em ordem de preferência
        const endpoints = [
            { url: BACKEND_URL, endpoint: '/code/run', name: 'API Pública' },
            { url: BACKEND_FALLBACK, endpoint: '/code/run', name: 'API Local' },
            { url: CODE_RUNNER_DIRECT, endpoint: '/api/v2/execute', name: 'Code Runner Direto', format: 'v2' }
        ];

        for (const { url, endpoint, name, format } of endpoints) {
            try {
                const body = format === 'v2'
                    ? { language: 'python', version: '3.11', files: [{ content: code }] }
                    : { language: 'python', code: code };

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 35000);

                const response = await fetch(`${url}${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

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
                console.log(`❌ ${name} falhou: ${e.message}`);
                continue;
            }
        }

        throw new Error('❌ Nenhum backend respondeu. O servidor pode estar offline.');
    }

    // Generate code with AI via API
    async function generateCodeWithAI(prompt) {
        const urls = [
            { url: BACKEND_URL, endpoint: '/code/generate' },
            { url: BACKEND_FALLBACK, endpoint: '/code/generate' }
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

    async function generateCodeWithAIStream(prompt, onChunk) {
        const urls = [
            { url: BACKEND_URL, endpoint: '/code/generate-stream' },
            { url: BACKEND_FALLBACK, endpoint: '/code/generate-stream' }
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

    // Run Python code via Pyodide (local) - DESABILITADO POR SEGURANÇA
    async function runCodePyodide(code) {
        // Pyodide não suporta operações de arquivo seguramente
        // Use o backend ou considere usar JupyterLite
        throw new Error('🔴 Execução local (Pyodide) desabilitada. Use o servidor Web.\n\nO servidor está em: http://192.168.15.2:2000');
    }

    // Run Python code (BACKEND ONLY - Pyodide desabilitado)
    async function runCode() {
        if (!editor) return;

        const code = editor.getValue();
        const output = document.getElementById('output');

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

    async function handleAIPromptRun() {
        const promptEl = document.getElementById('aiPrompt');
        const output = document.getElementById('output');

        if (!promptEl || !promptEl.value.trim()) {
            output.textContent = '⚠️ Descreva o que deseja fazer com a IA.';
            updateStatus('Aguardando prompt');
            return;
        }

        const current = editor ? editor.getValue() : '';
        const fileName = currentFile || 'main.py';
        const instruction = [
            'Você é um assistente estilo Copilot.',
            'Pode gerar um novo código ou alterar o existente.',
            'Se alterar o arquivo atual, retorne o conteúdo completo do arquivo atualizado.',
            'Se precisar criar múltiplos arquivos, use o formato:',
            '# FILE: nome_do_arquivo.py',
            '<conteúdo>',
            '# FILE: outro_arquivo.py',
            '<conteúdo>',
            'Não inclua explicações, apenas o conteúdo de código.'
        ].join('\n');

        const fullPrompt = `${instruction}\n\nPROMPT DO USUÁRIO:\n${promptEl.value.trim()}\n\nARQUIVO ATUAL (${fileName}):\n${current}`;

        updateStatus('Executando prompt com IA...');
        output.textContent = '🧠 Aplicando alterações com IA (stream)...\n';

        try {
            let code = '';
            try {
                code = await generateCodeWithAIStream(fullPrompt, (fullCode) => {
                    if (editor) {
                        editor.setValue(fullCode);
                        const file = getCurrentFile();
                        if (file) {
                            file.content = editor.getValue();
                            saveFiles();
                        }
                    }
                });
            } catch (streamError) {
                code = await generateCodeWithAI(fullPrompt);
                if (editor) {
                    editor.setValue(code);
                    const file = getCurrentFile();
                    if (file) {
                        file.content = editor.getValue();
                        saveFiles();
                    }
                }
            }

            const parsedFiles = parseFilesFromAI(code);
            if (parsedFiles.length > 0) {
                applyFiles(parsedFiles);
            } else if (editor) {
                editor.setValue(code);
                const file = getCurrentFile();
                if (file) {
                    file.content = editor.getValue();
                    saveFiles();
                }
            }

            updateStatus('Prompt aplicado');
            output.textContent = '✅ IA aplicou o prompt.';
        } catch (error) {
            console.error('Erro IA:', error);
            output.textContent = `❌ Erro ao aplicar prompt: ${error.message}`;
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

        const filePrompt = `${promptEl.value.trim()}\n\nRetorne no formato:\n# FILE: main.py\n<codigo>\n# FILE: utils.py\n<codigo>\nSem explicações.`;

        updateStatus('Gerando arquivos...');
        output.textContent = '🧠 Gerando arquivos com IA (stream)...\n';

        try {
            let text = '';
            try {
                text = await generateCodeWithAIStream(filePrompt, (fullCode) => {
                    if (editor) {
                        editor.setValue(fullCode);
                    }
                });
            } catch (streamError) {
                text = await generateCodeWithAI(filePrompt);
            }

            const newFiles = parseFilesFromAI(text);
            if (!newFiles.length) {
                // fallback: single file
                applyFiles([{ name: 'main.py', content: text }]);
            } else {
                applyFiles(newFiles);
            }

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
        if (editor) {
            editor.setValue(code.replace(/\\n/g, '\n'));
            const file = getCurrentFile();
            if (file) {
                file.content = editor.getValue();
                saveFiles();
            }
            updateStatus('Exemplo carregado');
        }
    }

    // Initialize when DOM is ready
    function init() {
        // Only initialize if IDE section exists
        const idePanel = document.getElementById('ide');
        if (!idePanel) return;

        // Fix: Garantir layout flex do container
        const container = document.querySelector('.ide-container');
        if (container) {
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
        }

        // Check backend availability on startup
        checkBackend().then(available => {
            console.log('Backend disponível:', available);
            updateStatus(available ? 'Servidor pronto' : 'Modo local');
        });

        // Initialize Monaco when IDE tab is clicked (lazy load)
        const ideTab = document.querySelector('[data-target="ide"]');
        if (ideTab) {
            ideTab.addEventListener('click', () => {
                if (!editor) {
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
                        'Endereço esperado: http://192.168.15.2:2000\n\n' +
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
