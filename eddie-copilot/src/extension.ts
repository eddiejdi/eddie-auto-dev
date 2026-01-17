import * as vscode from 'vscode';
import { OllamaClient } from './ollamaClient';
import { InlineCompletionProvider } from './inlineCompletionProvider';
import { ChatViewProvider } from './chatViewProvider';
import { StatusBarManager } from './statusBar';
import { CodeActionProvider } from './codeActionProvider';

let ollamaClient: OllamaClient;
let inlineProvider: InlineCompletionProvider;
let chatViewProvider: ChatViewProvider;
let statusBarManager: StatusBarManager;
let isEnabled = true;

export async function activate(context: vscode.ExtensionContext) {
    console.log('Eddie Copilot is activating...');

    // Initialize configuration
    const config = vscode.workspace.getConfiguration('eddie-copilot');
    isEnabled = config.get('enable', true);

    // Initialize Ollama client
    ollamaClient = new OllamaClient(config);

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
}

export function deactivate() {
    console.log('Eddie Copilot deactivated');
}
