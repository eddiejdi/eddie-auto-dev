import * as vscode from 'vscode';

/**
 * Cliente para intermediação entre modelo local leve e servidor Open WebUI remoto.
 * 
 * Estratégia:
 * - Tarefas simples (autocomplete curto): Modelo local leve (qwen2.5-coder:1.5b)
 * - Tarefas complexas (chat, refactoring): Servidor remoto via Open WebUI
 */

interface ChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

interface OpenWebUIRequest {
    model: string;
    messages: ChatMessage[];
    stream?: boolean;
    options?: {
        temperature?: number;
        num_predict?: number;
    };
}

export class HomelabClient {
    private ollamaUrl: string;
    private remoteUrl: string;
    private apiKey: string;
    private localModel: string;
    private remoteModel: string;
    private useRemote: boolean;
    private complexityThreshold: number;

    constructor(config: vscode.WorkspaceConfiguration) {
        // Ollama local para tarefas rápidas
        this.localModel = config.get('localModel', 'qwen2.5-coder:1.5b');
        
        // Servidor remoto Open WebUI para tarefas complexas
        this.apiKey = config.get('apiKey', '');
        this.remoteModel = config.get('remoteModel', 'eddie-coder:latest');
        
        // Configurações de roteamento
            this.ollamaUrl = config.get('ollamaUrl', process.env.OLLAMA_URL || `http://${process.env.HOMELAB_HOST || 'localhost'}:11434`);
            this.remoteUrl = config.get('remoteUrl', process.env.REMOTE_URL || `http://${process.env.HOMELAB_HOST || 'localhost'}:3000`);
        this.useRemote = config.get('useRemote', true);
        this.complexityThreshold = config.get('complexityThreshold', 100);
    }

    updateConfig(config: vscode.WorkspaceConfiguration) {
        this.ollamaUrl = config.get('ollamaUrl', 'http://192.168.15.2:11434');
        this.localModel = config.get('localModel', 'qwen2.5-coder:1.5b');
        this.remoteUrl = config.get('remoteUrl', 'http://192.168.15.2:3000');
        this.apiKey = config.get('apiKey', '');
        this.remoteModel = config.get('remoteModel', 'eddie-coder:latest');
        this.useRemote = config.get('useRemote', true);
        this.complexityThreshold = config.get('complexityThreshold', 100);
    }

    /**
     * Verifica conexão com Ollama local
     */
    async checkLocalConnection(): Promise<boolean> {
        try {
            const response = await fetch(`${this.ollamaUrl}/api/tags`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return response.ok;
        } catch (error) {
            console.error('Ollama local connection error:', error);
            return false;
        }
    }

    /**
     * Verifica conexão com servidor remoto
     */
    async checkRemoteConnection(): Promise<boolean> {
        if (!this.apiKey) {
            return false;
        }
        try {
            const response = await fetch(`${this.remoteUrl}/ollama/api/tags`, {
                method: 'GET',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`
                }
            });
            return response.ok;
        } catch (error) {
            console.error('Remote server connection error:', error);
            return false;
        }
    }

    /**
     * Determina se deve usar servidor remoto baseado na complexidade
     */
    private shouldUseRemote(prompt: string, isChat: boolean): boolean {
        if (!this.useRemote || !this.apiKey) {
            return false;
        }
        
        // Chat sempre vai pro remoto (mais capaz)
        if (isChat) {
            return true;
        }
        
        // Autocomplete curto -> local
        if (prompt.length < this.complexityThreshold) {
            return false;
        }
        
        // Tarefas complexas -> remoto
        const complexPatterns = [
            /refactor/i,
            /explain/i,
            /document/i,
            /test/i,
            /fix/i,
            /optimize/i,
            /review/i
        ];
        
        return complexPatterns.some(pattern => pattern.test(prompt));
    }

    /**
     * Gera completion usando modelo local leve
     */
    async localComplete(
        prompt: string,
        systemPrompt: string,
        options: { temperature?: number; maxTokens?: number; stop?: string[] } = {}
    ): Promise<string | null> {
        try {
            const response = await fetch(`${this.ollamaUrl}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: this.localModel,
                    prompt: prompt,
                    system: systemPrompt,
                    stream: false,
                    options: {
                        temperature: options.temperature ?? 0.2,
                        num_predict: options.maxTokens ?? 200,
                        stop: options.stop ?? ['\n\n\n', '```']
                    }
                })
            });

            if (!response.ok) {
                console.error('Local API error:', response.status);
                return null;
            }

            const data = await response.json() as { response: string };
            return data.response;
        } catch (error) {
            console.error('Local complete error:', error);
            return null;
        }
    }

    /**
     * Gera completion usando servidor remoto
     */
    async remoteComplete(
        prompt: string,
        systemPrompt: string,
        options: { temperature?: number; maxTokens?: number } = {}
    ): Promise<string | null> {
        if (!this.apiKey) {
            console.warn('Remote API key not configured');
            return null;
        }

        try {
            const response = await fetch(`${this.remoteUrl}/ollama/api/generate`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`
                },
                body: JSON.stringify({
                    model: this.remoteModel,
                    prompt: prompt,
                    system: systemPrompt,
                    stream: false,
                    options: {
                        temperature: options.temperature ?? 0.3,
                        num_predict: options.maxTokens ?? 1000
                    }
                })
            });

            if (!response.ok) {
                console.error('Remote API error:', response.status);
                return null;
            }

            const data = await response.json() as { response: string };
            return data.response;
        } catch (error) {
            console.error('Remote complete error:', error);
            return null;
        }
    }

    /**
     * Chat com servidor remoto (streaming)
     */
    async remoteChat(
        messages: ChatMessage[],
        onChunk?: (chunk: string) => void,
        cancellationToken?: vscode.CancellationToken
    ): Promise<string> {
        if (!this.apiKey) {
            throw new Error('Remote API key not configured. Please set eddie-copilot.apiKey in settings.');
        }

        const request: OpenWebUIRequest = {
            model: this.remoteModel,
            messages: messages,
            stream: !!onChunk,
            options: {
                temperature: 0.7,
                num_predict: 2000
            }
        };

        try {
            const controller = new AbortController();
            
            if (cancellationToken) {
                cancellationToken.onCancellationRequested(() => {
                    controller.abort();
                });
            }

            const response = await fetch(`${this.remoteUrl}/ollama/api/chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`
                },
                body: JSON.stringify(request),
                signal: controller.signal
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`Remote API error: ${response.status} - ${error}`);
            }

            if (onChunk && response.body) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n').filter(line => line.trim());

                    for (const line of lines) {
                        try {
                            const json = JSON.parse(line) as { message?: { content: string }, done: boolean };
                            if (json.message?.content) {
                                fullResponse += json.message.content;
                                onChunk(json.message.content);
                            }
                        } catch {
                            // Ignore parse errors
                        }
                    }
                }

                return fullResponse;
            } else {
                const data = await response.json() as { message: { content: string } };
                return data.message.content;
            }
        } catch (error) {
            if ((error as Error).name === 'AbortError') {
                return '';
            }
            throw error;
        }
    }

    /**
     * Chat inteligente: local para consultas simples, remoto para complexas
     */
    async smartChat(
        messages: ChatMessage[],
        onChunk?: (chunk: string) => void,
        cancellationToken?: vscode.CancellationToken
    ): Promise<string> {
        const lastMessage = messages[messages.length - 1]?.content || '';
        
        // Sempre usar remoto para chat (mais qualidade)
        if (this.useRemote && this.apiKey) {
            try {
                return await this.remoteChat(messages, onChunk, cancellationToken);
            } catch (error) {
                console.warn('Remote chat failed, falling back to local:', error);
            }
        }

        // Fallback para local
        return await this.localChat(messages, onChunk);
    }

    /**
     * Chat usando Ollama local
     */
    async localChat(
        messages: ChatMessage[],
        onChunk?: (chunk: string) => void
    ): Promise<string> {
        try {
            const response = await fetch(`${this.ollamaUrl}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: this.localModel,
                    messages: messages,
                    stream: !!onChunk,
                    options: {
                        temperature: 0.7,
                        num_predict: 1000
                    }
                })
            });

            if (!response.ok) {
                throw new Error(`Local chat error: ${response.status}`);
            }

            if (onChunk && response.body) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n').filter(line => line.trim());

                    for (const line of lines) {
                        try {
                            const json = JSON.parse(line) as { message?: { content: string } };
                            if (json.message?.content) {
                                fullResponse += json.message.content;
                                onChunk(json.message.content);
                            }
                        } catch {
                            // Ignore
                        }
                    }
                }

                return fullResponse;
            } else {
                const data = await response.json() as { message: { content: string } };
                return data.message.content;
            }
        } catch (error) {
            console.error('Local chat error:', error);
            throw error;
        }
    }

    /**
     * Completion inteligente: local para curto, remoto para complexo
     */
    async smartComplete(
        prefix: string,
        suffix: string,
        language: string,
        filename: string,
        cancellationToken?: vscode.CancellationToken
    ): Promise<string | null> {
        const systemPrompt = this.buildSystemPrompt(language);
        const prompt = this.buildCompletionPrompt(prefix, suffix, language, filename);
        
        // Autocomplete sempre usa local (velocidade)
        const result = await this.localComplete(prompt, systemPrompt, {
            temperature: 0.2,
            maxTokens: 200,
            stop: ['\n\n\n', '```', '// End', '# End']
        });

        if (result) {
            return this.cleanCompletion(result, language);
        }

        return null;
    }

    private buildSystemPrompt(language: string): string {
        return `You are an expert ${language} programmer. Complete the code naturally.
Rules:
- Only output the completion code
- Match existing style
- No explanations
- Keep it concise`;
    }

    private buildCompletionPrompt(prefix: string, suffix: string, language: string, filename: string): string {
        return `File: ${filename}\nLanguage: ${language}\n\n${prefix}<CURSOR>${suffix}\n\nComplete at <CURSOR>:`;
    }

    private cleanCompletion(completion: string, language: string): string {
        let cleaned = completion.trim();
        
        // Remove markdown
        if (cleaned.startsWith('```')) {
            const lines = cleaned.split('\n');
            lines.shift();
            if (lines[lines.length - 1]?.trim() === '```') {
                lines.pop();
            }
            cleaned = lines.join('\n');
        }

        // Limit length
        const lines = cleaned.split('\n');
        if (lines.length > 15) {
            cleaned = lines.slice(0, 15).join('\n');
        }

        return cleaned;
    }

    /**
     * Retorna status da conexão
     */
    async getStatus(): Promise<{ local: boolean; remote: boolean; localModel: string; remoteModel: string }> {
        const local = await this.checkLocalConnection();
        const remote = await this.checkRemoteConnection();
        
        return {
            local,
            remote,
            localModel: this.localModel,
            remoteModel: this.remoteModel
        };
    }
}
