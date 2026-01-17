import * as vscode from 'vscode';
import { HomelabClient } from './homelabClient';

interface OllamaResponse {
    model: string;
    created_at: string;
    response: string;
    done: boolean;
    context?: number[];
    total_duration?: number;
    load_duration?: number;
    prompt_eval_count?: number;
    prompt_eval_duration?: number;
    eval_count?: number;
    eval_duration?: number;
}

interface OllamaGenerateRequest {
    model: string;
    prompt: string;
    stream?: boolean;
    options?: {
        temperature?: number;
        num_predict?: number;
        top_p?: number;
        top_k?: number;
        stop?: string[];
    };
    system?: string;
    context?: number[];
}

interface ChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

interface OllamaChatRequest {
    model: string;
    messages: ChatMessage[];
    stream?: boolean;
    options?: {
        temperature?: number;
        num_predict?: number;
        top_p?: number;
        top_k?: number;
    };
}

export class OllamaClient {
    private baseUrl: string;
    private model: string;
    private chatModel: string;
    private maxTokens: number;
    private temperature: number;
    private context: number[] | undefined;
    
    // Cliente integrado para Homelab (local + remoto)
    private homelabClient: HomelabClient;
    private useHomelab: boolean;

    constructor(config: vscode.WorkspaceConfiguration) {
        this.baseUrl = config.get('ollamaUrl', 'http://192.168.15.2:11434');
        this.model = config.get('model', 'qwen2.5-coder:1.5b');
        this.chatModel = config.get('chatModel', 'qwen2.5-coder:1.5b');
        this.maxTokens = config.get('maxTokens', 500);
        this.temperature = config.get('temperature', 0.2);
        
        // Inicializa cliente Homelab
        this.homelabClient = new HomelabClient(config);
        this.useHomelab = config.get('useHomelab', true);
    }

    updateConfig(config: vscode.WorkspaceConfiguration) {
        this.baseUrl = config.get('ollamaUrl', 'http://192.168.15.2:11434');
        this.model = config.get('model', 'qwen2.5-coder:1.5b');
        this.chatModel = config.get('chatModel', 'qwen2.5-coder:1.5b');
        this.maxTokens = config.get('maxTokens', 500);
        this.temperature = config.get('temperature', 0.2);
        
        this.homelabClient.updateConfig(config);
        this.useHomelab = config.get('useHomelab', true);
    }
    
    /**
     * Retorna o cliente Homelab para acesso direto
     */
    getHomelabClient(): HomelabClient {
        return this.homelabClient;
    }

    async checkConnection(): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/api/tags`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return response.ok;
        } catch (error) {
            console.error('Ollama connection error:', error);
            return false;
        }
    }

    async getModels(): Promise<string[]> {
        try {
            const response = await fetch(`${this.baseUrl}/api/tags`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                return [];
            }
            const data = await response.json() as { models: { name: string }[] };
            return data.models.map(m => m.name);
        } catch (error) {
            console.error('Error getting models:', error);
            return [];
        }
    }

    async complete(
        prefix: string,
        suffix: string,
        language: string,
        filename: string,
        cancellationToken?: vscode.CancellationToken
    ): Promise<string | null> {
        const systemPrompt = this.buildSystemPrompt(language);
        const prompt = this.buildCompletionPrompt(prefix, suffix, language, filename);

        const request: OllamaGenerateRequest = {
            model: this.model,
            prompt: prompt,
            stream: false,
            system: systemPrompt,
            options: {
                temperature: this.temperature,
                num_predict: this.maxTokens,
                top_p: 0.9,
                stop: ['\n\n\n', '```', '// End', '# End', '"""', "'''"]
            }
        };

        try {
            const controller = new AbortController();
            
            if (cancellationToken) {
                cancellationToken.onCancellationRequested(() => {
                    controller.abort();
                });
            }

            const response = await fetch(`${this.baseUrl}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
                signal: controller.signal
            });

            if (!response.ok) {
                console.error('Ollama API error:', response.status, response.statusText);
                return null;
            }

            const data = await response.json() as OllamaResponse;
            
            // Store context for follow-up completions
            this.context = data.context;

            // Clean up the response
            let completion = data.response;
            completion = this.cleanCompletion(completion, language);
            
            return completion;
        } catch (error) {
            if ((error as Error).name === 'AbortError') {
                return null;
            }
            console.error('Completion error:', error);
            return null;
        }
    }

    async chat(
        messages: ChatMessage[],
        onChunk?: (chunk: string) => void,
        cancellationToken?: vscode.CancellationToken
    ): Promise<string> {
        // Usar Homelab Client (roteamento inteligente local/remoto)
        if (this.useHomelab) {
            try {
                return await this.homelabClient.smartChat(messages, onChunk, cancellationToken);
            } catch (error) {
                console.warn('Homelab chat failed, falling back to direct Ollama:', error);
            }
        }
        
        // Fallback: Ollama direto
        const request: OllamaChatRequest = {
            model: this.chatModel,
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

            const response = await fetch(`${this.baseUrl}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
                signal: controller.signal
            });

            if (!response.ok) {
                throw new Error(`Ollama API error: ${response.status}`);
            }

            if (onChunk && response.body) {
                // Streaming response
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }

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
                            // Ignore parse errors for incomplete chunks
                        }
                    }
                }

                return fullResponse;
            } else {
                // Non-streaming response
                const data = await response.json() as { message: { content: string } };
                return data.message.content;
            }
        } catch (error) {
            if ((error as Error).name === 'AbortError') {
                return '';
            }
            console.error('Chat error:', error);
            throw error;
        }
    }

    private buildSystemPrompt(language: string): string {
        return `You are an expert ${language} programmer and AI coding assistant. 
You provide concise, accurate code completions.
Rules:
- Complete the code naturally where the cursor is
- Match the existing code style and indentation
- Only output the completion, no explanations
- Do not repeat code that already exists
- Keep completions focused and relevant
- Use proper ${language} syntax and best practices`;
    }

    private buildCompletionPrompt(prefix: string, suffix: string, language: string, filename: string): string {
        let prompt = `File: ${filename}\nLanguage: ${language}\n\n`;
        prompt += `<|prefix|>${prefix}<|suffix|>${suffix}<|middle|>`;
        return prompt;
    }

    private cleanCompletion(completion: string, language: string): string {
        // Remove common artifacts
        completion = completion.trim();
        
        // Remove markdown code blocks if present
        if (completion.startsWith('```')) {
            const lines = completion.split('\n');
            lines.shift(); // Remove opening ```
            if (lines[lines.length - 1]?.trim() === '```') {
                lines.pop(); // Remove closing ```
            }
            completion = lines.join('\n');
        }

        // Remove leading/trailing quotes sometimes added by models
        if ((completion.startsWith('"') && completion.endsWith('"')) ||
            (completion.startsWith("'") && completion.endsWith("'"))) {
            completion = completion.slice(1, -1);
        }

        // Limit to reasonable length (avoid runaway completions)
        const lines = completion.split('\n');
        if (lines.length > 20) {
            completion = lines.slice(0, 20).join('\n');
        }

        return completion;
    }
}
