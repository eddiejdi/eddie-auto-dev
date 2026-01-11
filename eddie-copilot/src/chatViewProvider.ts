import * as vscode from 'vscode';
import { OllamaClient } from './ollamaClient';

interface ChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

export class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'eddie-copilot.chatView';

    private _view?: vscode.WebviewView;
    private ollamaClient: OllamaClient;
    private config: vscode.WorkspaceConfiguration;
    private chatHistory: ChatMessage[] = [];
    private isProcessing = false;

    constructor(
        private readonly extensionUri: vscode.Uri,
        ollamaClient: OllamaClient,
        config: vscode.WorkspaceConfiguration
    ) {
        this.ollamaClient = ollamaClient;
        this.config = config;
        
        // Initialize with system message
        this.chatHistory.push({
            role: 'system',
            content: `You are Eddie Copilot, an expert AI coding assistant. You help developers write, debug, explain, and improve code. 
You provide clear, concise, and accurate responses.
When providing code, always use proper markdown code blocks with language specification.
Be helpful, friendly, and professional.`
        });
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri]
        };

        webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'sendMessage':
                    await this.handleUserMessage(data.message);
                    break;
                case 'clearHistory':
                    this.clearHistory();
                    break;
                case 'insertCode':
                    this.insertCodeToEditor(data.code);
                    break;
                case 'copyCode':
                    await vscode.env.clipboard.writeText(data.code);
                    vscode.window.showInformationMessage('Code copied to clipboard');
                    break;
            }
        });
    }

    public async sendMessage(message: string) {
        if (this._view) {
            this._view.webview.postMessage({ type: 'userMessage', message });
            await this.handleUserMessage(message);
        }
    }

    private async handleUserMessage(message: string) {
        if (this.isProcessing) {
            return;
        }

        this.isProcessing = true;

        // Add user message to history
        this.chatHistory.push({ role: 'user', content: message });

        // Show loading state
        this._view?.webview.postMessage({ type: 'startResponse' });

        try {
            // Get current editor context if available
            const editor = vscode.window.activeTextEditor;
            let contextMessage = message;
            
            if (editor) {
                const language = editor.document.languageId;
                const filename = editor.document.fileName.split(/[/\\]/).pop();
                contextMessage = `[Context: File "${filename}", Language: ${language}]\n\n${message}`;
            }

            // Stream the response
            let fullResponse = '';
            await this.ollamaClient.chat(
                [...this.chatHistory.slice(0, -1), { role: 'user', content: contextMessage }],
                (chunk) => {
                    fullResponse += chunk;
                    this._view?.webview.postMessage({ 
                        type: 'responseChunk', 
                        chunk: chunk 
                    });
                }
            );

            // Add assistant response to history
            this.chatHistory.push({ role: 'assistant', content: fullResponse });

            // Signal end of response
            this._view?.webview.postMessage({ type: 'endResponse' });

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            this._view?.webview.postMessage({ 
                type: 'error', 
                message: `Error: ${errorMessage}` 
            });
        } finally {
            this.isProcessing = false;
        }
    }

    public clearHistory() {
        this.chatHistory = [{
            role: 'system',
            content: `You are Eddie Copilot, an expert AI coding assistant. You help developers write, debug, explain, and improve code.`
        }];
        this._view?.webview.postMessage({ type: 'clearChat' });
    }

    private insertCodeToEditor(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            editor.edit((editBuilder) => {
                editBuilder.insert(editor.selection.active, code);
            });
        } else {
            vscode.window.showWarningMessage('No active editor to insert code');
        }
    }

    private getHtmlForWebview(webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'unsafe-inline';">
    <title>Eddie Copilot Chat</title>
    <style>
        :root {
            --bg-color: var(--vscode-editor-background);
            --text-color: var(--vscode-editor-foreground);
            --input-bg: var(--vscode-input-background);
            --input-border: var(--vscode-input-border);
            --button-bg: var(--vscode-button-background);
            --button-fg: var(--vscode-button-foreground);
            --button-hover: var(--vscode-button-hoverBackground);
            --user-msg-bg: var(--vscode-textBlockQuote-background);
            --assistant-msg-bg: var(--vscode-editor-inactiveSelectionBackground);
            --code-bg: var(--vscode-textCodeBlock-background);
            --border-color: var(--vscode-panel-border);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--text-color);
            background-color: var(--bg-color);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            padding: 10px 15px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h3 {
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .header-icon {
            font-size: 18px;
        }

        .clear-btn {
            background: transparent;
            border: none;
            color: var(--text-color);
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
        }

        .clear-btn:hover {
            background: var(--button-bg);
            color: var(--button-fg);
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .message {
            padding: 10px 14px;
            border-radius: 8px;
            max-width: 95%;
            word-wrap: break-word;
            line-height: 1.5;
        }

        .user-message {
            background: var(--user-msg-bg);
            align-self: flex-end;
            border-bottom-right-radius: 2px;
        }

        .assistant-message {
            background: var(--assistant-msg-bg);
            align-self: flex-start;
            border-bottom-left-radius: 2px;
        }

        .message pre {
            background: var(--code-bg);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
            position: relative;
        }

        .message code {
            font-family: var(--vscode-editor-font-family);
            font-size: 13px;
        }

        .message p {
            margin: 6px 0;
        }

        .code-block-wrapper {
            position: relative;
        }

        .code-actions {
            position: absolute;
            top: 4px;
            right: 4px;
            display: flex;
            gap: 4px;
        }

        .code-action-btn {
            background: var(--button-bg);
            color: var(--button-fg);
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            opacity: 0.8;
        }

        .code-action-btn:hover {
            opacity: 1;
            background: var(--button-hover);
        }

        .loading {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--vscode-descriptionForeground);
            padding: 10px;
        }

        .loading-dots {
            display: flex;
            gap: 4px;
        }

        .loading-dots span {
            width: 6px;
            height: 6px;
            background: var(--text-color);
            border-radius: 50%;
            animation: bounce 1.4s ease-in-out infinite both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        .input-container {
            padding: 12px 15px;
            border-top: 1px solid var(--border-color);
            display: flex;
            gap: 8px;
        }

        .input-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        #messageInput {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--input-border);
            border-radius: 6px;
            background: var(--input-bg);
            color: var(--text-color);
            font-family: inherit;
            font-size: 13px;
            resize: none;
            min-height: 60px;
            max-height: 150px;
        }

        #messageInput:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }

        #sendButton {
            background: var(--button-bg);
            color: var(--button-fg);
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            align-self: flex-end;
        }

        #sendButton:hover {
            background: var(--button-hover);
        }

        #sendButton:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .welcome-message {
            text-align: center;
            color: var(--vscode-descriptionForeground);
            padding: 20px;
        }

        .welcome-message h4 {
            margin-bottom: 10px;
            color: var(--text-color);
        }

        .welcome-message p {
            font-size: 12px;
            margin: 4px 0;
        }

        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 12px;
            justify-content: center;
        }

        .suggestion-chip {
            background: var(--user-msg-bg);
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            border-radius: 16px;
            font-size: 11px;
            cursor: pointer;
        }

        .suggestion-chip:hover {
            background: var(--assistant-msg-bg);
        }

        .error-message {
            background: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            color: var(--vscode-errorForeground);
            padding: 10px;
            border-radius: 6px;
            margin: 8px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h3><span class="header-icon">🤖</span> Eddie Copilot</h3>
        <button class="clear-btn" onclick="clearChat()">Clear</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="welcome-message">
            <h4>👋 Welcome to Eddie Copilot!</h4>
            <p>I'm your AI coding assistant powered by Ollama.</p>
            <p>Ask me anything about code!</p>
            <div class="suggestions">
                <span class="suggestion-chip" onclick="sendSuggestion('Explain this code')">Explain code</span>
                <span class="suggestion-chip" onclick="sendSuggestion('Fix bugs in my code')">Fix bugs</span>
                <span class="suggestion-chip" onclick="sendSuggestion('Write unit tests')">Write tests</span>
                <span class="suggestion-chip" onclick="sendSuggestion('Refactor this code')">Refactor</span>
            </div>
        </div>
    </div>

    <div class="input-container">
        <div class="input-wrapper">
            <textarea 
                id="messageInput" 
                placeholder="Ask Eddie anything... (Shift+Enter for new line)"
                rows="2"
            ></textarea>
            <button id="sendButton" onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const chatContainer = document.getElementById('chatContainer');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        
        let currentAssistantMessage = null;
        let isWaitingForResponse = false;

        // Handle keyboard shortcuts
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || isWaitingForResponse) return;

            addUserMessage(message);
            messageInput.value = '';
            
            vscode.postMessage({ type: 'sendMessage', message });
        }

        function sendSuggestion(text) {
            messageInput.value = text;
            messageInput.focus();
        }

        function addUserMessage(message) {
            // Remove welcome message if present
            const welcome = chatContainer.querySelector('.welcome-message');
            if (welcome) welcome.remove();

            const div = document.createElement('div');
            div.className = 'message user-message';
            div.textContent = message;
            chatContainer.appendChild(div);
            scrollToBottom();
        }

        function addAssistantMessage() {
            const div = document.createElement('div');
            div.className = 'message assistant-message';
            chatContainer.appendChild(div);
            currentAssistantMessage = div;
            scrollToBottom();
            return div;
        }

        function showLoading() {
            const loading = document.createElement('div');
            loading.className = 'loading';
            loading.id = 'loadingIndicator';
            loading.innerHTML = \`
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <span>Thinking...</span>
            \`;
            chatContainer.appendChild(loading);
            scrollToBottom();
        }

        function hideLoading() {
            const loading = document.getElementById('loadingIndicator');
            if (loading) loading.remove();
        }

        function formatMessage(text) {
            // Convert markdown code blocks to HTML
            text = text.replace(/\`\`\`(\w*)\n([\s\S]*?)\`\`\`/g, (match, lang, code) => {
                const escapedCode = escapeHtml(code.trim());
                return \`<div class="code-block-wrapper">
                    <pre><code class="language-\${lang}">\${escapedCode}</code></pre>
                    <div class="code-actions">
                        <button class="code-action-btn" onclick="copyCode(this)">Copy</button>
                        <button class="code-action-btn" onclick="insertCode(this)">Insert</button>
                    </div>
                </div>\`;
            });

            // Convert inline code
            text = text.replace(/\`([^\`]+)\`/g, '<code>$1</code>');

            // Convert line breaks to paragraphs
            text = text.split('\\n\\n').map(p => \`<p>\${p}</p>\`).join('');
            text = text.replace(/\\n/g, '<br>');

            return text;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function copyCode(button) {
            const code = button.closest('.code-block-wrapper').querySelector('code').textContent;
            vscode.postMessage({ type: 'copyCode', code });
        }

        function insertCode(button) {
            const code = button.closest('.code-block-wrapper').querySelector('code').textContent;
            vscode.postMessage({ type: 'insertCode', code });
        }

        function clearChat() {
            vscode.postMessage({ type: 'clearHistory' });
        }

        function scrollToBottom() {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Handle messages from extension
        window.addEventListener('message', (event) => {
            const data = event.data;

            switch (data.type) {
                case 'userMessage':
                    addUserMessage(data.message);
                    break;

                case 'startResponse':
                    isWaitingForResponse = true;
                    sendButton.disabled = true;
                    showLoading();
                    addAssistantMessage();
                    break;

                case 'responseChunk':
                    hideLoading();
                    if (currentAssistantMessage) {
                        currentAssistantMessage.textContent += data.chunk;
                        scrollToBottom();
                    }
                    break;

                case 'endResponse':
                    isWaitingForResponse = false;
                    sendButton.disabled = false;
                    if (currentAssistantMessage) {
                        currentAssistantMessage.innerHTML = formatMessage(currentAssistantMessage.textContent);
                    }
                    currentAssistantMessage = null;
                    scrollToBottom();
                    break;

                case 'error':
                    hideLoading();
                    isWaitingForResponse = false;
                    sendButton.disabled = false;
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error-message';
                    errorDiv.textContent = data.message;
                    chatContainer.appendChild(errorDiv);
                    currentAssistantMessage = null;
                    scrollToBottom();
                    break;

                case 'clearChat':
                    chatContainer.innerHTML = \`
                        <div class="welcome-message">
                            <h4>👋 Welcome to Eddie Copilot!</h4>
                            <p>I'm your AI coding assistant powered by Ollama.</p>
                            <p>Ask me anything about code!</p>
                            <div class="suggestions">
                                <span class="suggestion-chip" onclick="sendSuggestion('Explain this code')">Explain code</span>
                                <span class="suggestion-chip" onclick="sendSuggestion('Fix bugs in my code')">Fix bugs</span>
                                <span class="suggestion-chip" onclick="sendSuggestion('Write unit tests')">Write tests</span>
                                <span class="suggestion-chip" onclick="sendSuggestion('Refactor this code')">Refactor</span>
                            </div>
                        </div>
                    \`;
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}
