import * as vscode from 'vscode';
import { OllamaClient } from './ollamaClient';
import { InlineCompletionProvider } from './inlineCompletionProvider';
import { ChatViewProvider } from './chatViewProvider';
import { StatusBarManager } from './statusBar';
import { CodeActionProvider } from './codeActionProvider';
import { HomelabAgentClient } from './homelabAgentClient';

let ollamaClient: OllamaClient;
let inlineProvider: InlineCompletionProvider;
let chatViewProvider: ChatViewProvider;
let statusBarManager: StatusBarManager;
let homelabAgentClient: HomelabAgentClient;
let isEnabled = true;

export async function activate(context: vscode.ExtensionContext) {
    console.log('Eddie Copilot is activating...');

    // Initialize configuration
    const config = vscode.workspace.getConfiguration('eddie-copilot');
    isEnabled = config.get('enable', true);

    // Initialize Ollama client
    ollamaClient = new OllamaClient(config);

    // Initialize Homelab Agent client
    homelabAgentClient = new HomelabAgentClient(config);

    // Initialize status bar
    statusBarManager = new StatusBarManager();
    context.subscriptions.push(statusBarManager);

    // Check Ollama connection
    await checkConnections(config);

    // Initialize inline completion provider
    inlineProvider = new InlineCompletionProvider(ollamaClient, config);
    
    // Register inline completion provider for all languages
    const inlineDisposable = vscode.languages.registerInlineCompletionItemProvider(
        { pattern: '**' },
        inlineProvider
    );
    context.subscriptions.push(inlineDisposable);

    // Initialize chat view provider
    chatViewProvider = new ChatViewProvider(context.extensionUri, ollamaClient, config);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('eddie-copilot.chatView', chatViewProvider)
    );

    // Initialize code action provider
    const codeActionProvider = new CodeActionProvider(ollamaClient);
    context.subscriptions.push(
        vscode.languages.registerCodeActionsProvider({ pattern: '**' }, codeActionProvider, {
            providedCodeActionKinds: CodeActionProvider.providedCodeActionKinds
        })
    );

    // Register commands
    registerCommands(context);

    // Watch for configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(async e => {
            if (e.affectsConfiguration('eddie-copilot')) {
                const newConfig = vscode.workspace.getConfiguration('eddie-copilot');
                ollamaClient.updateConfig(newConfig);
                inlineProvider.updateConfig(newConfig);
                isEnabled = newConfig.get('enable', true);
                
                if (isEnabled) {
                    statusBarManager.setEnabled();
                    await checkConnections(newConfig);
                } else {
                    statusBarManager.setDisabled();
                }
            }
        })
    );

    console.log('Eddie Copilot activated successfully!');
}

async function checkConnections(config: vscode.WorkspaceConfiguration) {
    const homelabClient = ollamaClient.getHomelabClient();
    const status = await homelabClient.getStatus();
    
    if (status.local) {
        statusBarManager.setConnected(status.localModel);
        console.log(`Eddie Copilot: Local connected (${status.localModel})`);
    } else {
        statusBarManager.setDisconnected();
        vscode.window.showWarningMessage('Eddie Copilot: Ollama local não conectado. Verifique se está rodando.');
    }
    
    if (status.remote) {
        statusBarManager.setRemoteConnected(status.remoteModel);
        console.log(`Eddie Copilot: Remote connected (${status.remoteModel})`);
    } else {
        statusBarManager.setRemoteDisconnected();
        const apiKey = config.get<string>('apiKey', '');
        if (!apiKey) {
            console.log('Eddie Copilot: Remote not configured (no API key)');
        }
    }
}

function registerCommands(context: vscode.ExtensionContext) {
    // Show status command
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.showStatus', async () => {
            const homelabClient = ollamaClient.getHomelabClient();
            const status = await homelabClient.getStatus();
            
            const localStatus = status.local ? `✅ Conectado (${status.localModel})` : '❌ Desconectado';
            const remoteStatus = status.remote ? `✅ Conectado (${status.remoteModel})` : '❌ Desconectado';
            
            const message = `Eddie Copilot Status\n\n` +
                `🖥️ Local: ${localStatus}\n` +
                `☁️ Remoto: ${remoteStatus}`;
            
            const action = await vscode.window.showInformationMessage(
                message,
                'Configurar API Key',
                'Abrir Configurações',
                'Fechar'
            );
            
            if (action === 'Configurar API Key') {
                const apiKey = await vscode.window.showInputBox({
                    prompt: 'Digite a API Key do Open WebUI',
                    password: true,
                    placeHolder: 'sk-...'
                });
                if (apiKey) {
                    await vscode.workspace.getConfiguration('eddie-copilot').update('apiKey', apiKey, true);
                    vscode.window.showInformationMessage('API Key salva! Reconectando...');
                    const config = vscode.workspace.getConfiguration('eddie-copilot');
                    await checkConnections(config);
                }
            } else if (action === 'Abrir Configurações') {
                await vscode.commands.executeCommand('workbench.action.openSettings', 'eddie-copilot');
            }
        })
    );


    // Select model command (fetch models from local and remote servers)
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.selectModel', async () => {
            const config = vscode.workspace.getConfiguration('eddie-copilot');
            const homelabClient = ollamaClient.getHomelabClient();

            const target = await vscode.window.showQuickPick(['Set Local Model', 'Set Remote Model'], {
                placeHolder: 'Escolha onde salvar o modelo'
            });
            if (!target) return;

            let models: string[] = [];
            if (target === 'Set Local Model') {
                models = await homelabClient.getLocalModels();
                // fallback to Ollama client if needed
                if (!models || models.length === 0) {
                    models = await ollamaClient.getModels();
                }
            } else {
                models = await homelabClient.getRemoteModels();
            }

            if (!models || models.length === 0) {
                vscode.window.showWarningMessage('Nenhum modelo encontrado no servidor selecionado. Verifique a conexão e a API Key.');
                return;
            }

            const choice = await vscode.window.showQuickPick(models, { placeHolder: 'Selecione o modelo' });
            if (!choice) return;

            const key = target === 'Set Local Model' ? 'localModel' : 'remoteModel';
            await config.update(key, choice, true);
            vscode.window.showInformationMessage(`Configuração atualizada: ${key} = ${choice}`);

            // Re-check connections/status to update UI
            await checkConnections(config);
        })
    );
    // Enable/Disable commands
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.enable', () => {
            vscode.workspace.getConfiguration('eddie-copilot').update('enable', true, true);
            isEnabled = true;
            statusBarManager.setEnabled();
            vscode.window.showInformationMessage('Eddie Copilot enabled');
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.disable', () => {
            vscode.workspace.getConfiguration('eddie-copilot').update('enable', false, true);
            isEnabled = false;
            statusBarManager.setDisabled();
            vscode.window.showInformationMessage('Eddie Copilot disabled');
        })
    );

    // Trigger inline suggestion manually
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.triggerInline', async () => {
            if (!isEnabled) {
                return;
            }
            await vscode.commands.executeCommand('editor.action.inlineSuggest.trigger');
        })
    );

    // Accept suggestion
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.acceptSuggestion', async () => {
            await vscode.commands.executeCommand('editor.action.inlineSuggest.commit');
        })
    );

    // Next/Previous suggestion
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.nextSuggestion', async () => {
            await vscode.commands.executeCommand('editor.action.inlineSuggest.showNext');
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.previousSuggestion', async () => {
            await vscode.commands.executeCommand('editor.action.inlineSuggest.showPrevious');
        })
    );

    // Dismiss suggestion
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.dismissSuggestion', async () => {
            await vscode.commands.executeCommand('editor.action.inlineSuggest.hide');
        })
    );

    // Open chat
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.openChat', async () => {
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Explain code
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.explainCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('Please select some code first');
                return;
            }
            chatViewProvider.sendMessage(`Explain this code:\n\`\`\`\n${selection}\n\`\`\``);
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Fix code
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.fixCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('Please select some code first');
                return;
            }
            chatViewProvider.sendMessage(`Fix any issues in this code:\n\`\`\`\n${selection}\n\`\`\``);
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Generate tests
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.generateTests', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('Please select some code first');
                return;
            }
            const language = editor.document.languageId;
            chatViewProvider.sendMessage(`Generate unit tests for this ${language} code:\n\`\`\`${language}\n${selection}\n\`\`\``);
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Add documentation
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.addDocumentation', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('Please select some code first');
                return;
            }
            const language = editor.document.languageId;
            chatViewProvider.sendMessage(`Add documentation/comments to this ${language} code:\n\`\`\`${language}\n${selection}\n\`\`\``);
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Refactor code
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.refactorCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('Please select some code first');
                return;
            }
            const language = editor.document.languageId;
            chatViewProvider.sendMessage(`Refactor and improve this ${language} code:\n\`\`\`${language}\n${selection}\n\`\`\``);
            await vscode.commands.executeCommand('eddie-copilot.chatView.focus');
        })
    );

    // Clear chat history
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.clearHistory', () => {
            chatViewProvider.clearHistory();
            vscode.window.showInformationMessage('Chat history cleared');
        })
    );

    // ---- Homelab Agent Commands ----

    // Homelab: Execute command
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabExecute', async () => {
            const command = await vscode.window.showInputBox({
                prompt: 'Comando a executar no homelab (rede local)',
                placeHolder: 'docker ps / systemctl status nginx / uptime ...',
            });
            if (!command) {return;}

            try {
                const result = await homelabAgentClient.execute(command);
                const output = vscode.window.createOutputChannel('Eddie Homelab');
                output.clear();
                output.appendLine(`$ ${command}`);
                output.appendLine(`Exit code: ${result.exit_code} | Duration: ${result.duration_ms}ms`);
                output.appendLine('---');
                if (result.stdout) {output.appendLine(result.stdout);}
                if (result.stderr) {output.appendLine(`STDERR: ${result.stderr}`);}
                if (result.error) {output.appendLine(`ERROR: ${result.error}`);}
                output.show(true);
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Server health
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabHealth', async () => {
            try {
                const health = await homelabAgentClient.getServerHealth();
                if (!health) {
                    vscode.window.showWarningMessage('Homelab: servidor indisponível');
                    return;
                }
                const items = [
                    `Status: ${health.status}`,
                    `Hostname: ${health.hostname || 'N/A'}`,
                    `Uptime: ${health.uptime || 'N/A'}`,
                    `Memory: ${health.memory || 'N/A'}`,
                    `Disk: ${health.disk || 'N/A'}`,
                    `CPU Load: ${health.cpu_load || 'N/A'}`,
                    `Kernel: ${health.kernel || 'N/A'}`,
                ];
                vscode.window.showQuickPick(items, { placeHolder: '🖥️ Homelab Server Health' });
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Docker PS
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabDockerPs', async () => {
            try {
                const result = await homelabAgentClient.dockerPs(true);
                const output = vscode.window.createOutputChannel('Eddie Homelab');
                output.clear();
                output.appendLine('🐳 Docker Containers (homelab)');
                output.appendLine('---');
                output.appendLine(result.stdout || result.error || 'Sem dados');
                output.show(true);
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Docker Logs
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabDockerLogs', async () => {
            const container = await vscode.window.showInputBox({
                prompt: 'Nome ou ID do container',
                placeHolder: 'eddie-postgres',
            });
            if (!container) {return;}

            try {
                const result = await homelabAgentClient.dockerLogs(container, 100);
                const output = vscode.window.createOutputChannel('Eddie Homelab');
                output.clear();
                output.appendLine(`🐳 Logs: ${container}`);
                output.appendLine('---');
                output.appendLine(result.stdout || result.error || 'Sem logs');
                output.show(true);
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Systemd Status
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabSystemdStatus', async () => {
            const service = await vscode.window.showInputBox({
                prompt: 'Nome do serviço systemd',
                placeHolder: 'eddie-telegram-bot / specialized-agents-api / nginx',
            });
            if (!service) {return;}

            try {
                const result = await homelabAgentClient.systemdStatus(service);
                const output = vscode.window.createOutputChannel('Eddie Homelab');
                output.clear();
                output.appendLine(`⚙️ systemctl status ${service}`);
                output.appendLine('---');
                output.appendLine(result.stdout || result.error || 'Sem dados');
                output.show(true);
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Systemd Restart
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabSystemdRestart', async () => {
            const service = await vscode.window.showInputBox({
                prompt: 'Nome do serviço systemd para reiniciar',
                placeHolder: 'eddie-telegram-bot',
            });
            if (!service) {return;}

            const confirm = await vscode.window.showWarningMessage(
                `Reiniciar serviço "${service}" no homelab?`,
                { modal: true },
                'Sim, reiniciar'
            );
            if (confirm !== 'Sim, reiniciar') {return;}

            try {
                const result = await homelabAgentClient.systemdRestart(service);
                if (result.success) {
                    vscode.window.showInformationMessage(`✅ Serviço "${service}" reiniciado com sucesso`);
                } else {
                    vscode.window.showErrorMessage(`❌ Falha ao reiniciar "${service}": ${result.error || result.stderr}`);
                }
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );

    // Homelab: Journalctl logs
    context.subscriptions.push(
        vscode.commands.registerCommand('eddie-copilot.homelabLogs', async () => {
            const service = await vscode.window.showInputBox({
                prompt: 'Nome do serviço para ver logs (journalctl)',
                placeHolder: 'eddie-telegram-bot',
            });
            if (!service) {return;}

            try {
                const result = await homelabAgentClient.systemdLogs(service, 100);
                const output = vscode.window.createOutputChannel('Eddie Homelab');
                output.clear();
                output.appendLine(`📋 journalctl -u ${service} -n 100`);
                output.appendLine('---');
                output.appendLine(result.stdout || result.error || 'Sem logs');
                output.show(true);
            } catch (e: unknown) {
                vscode.window.showErrorMessage(`Homelab: ${e instanceof Error ? e.message : String(e)}`);
            }
        })
    );
}

export function deactivate() {
    console.log('Eddie Copilot deactivated');
}
