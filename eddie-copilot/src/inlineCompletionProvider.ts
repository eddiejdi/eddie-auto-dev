import * as vscode from 'vscode';
import { OllamaClient } from './ollamaClient';

interface CompletionCache {
    prefix: string;
    completion: string;
    timestamp: number;
}

export class InlineCompletionProvider implements vscode.InlineCompletionItemProvider {
    private ollamaClient: OllamaClient;
    private debounceTimer: NodeJS.Timeout | undefined;
    private debounceTime: number;
    private contextLines: number;
    private enableAutoComplete: boolean;
    private cache: Map<string, CompletionCache> = new Map();
    private readonly CACHE_TTL = 30000; // 30 seconds
    private isGenerating = false;
    private lastCompletionRequest: number = 0;
    private suggestions: vscode.InlineCompletionItem[] = [];
    private currentSuggestionIndex: number = 0;

    constructor(ollamaClient: OllamaClient, config: vscode.WorkspaceConfiguration) {
        this.ollamaClient = ollamaClient;
        this.debounceTime = config.get('debounceTime', 300);
        this.contextLines = config.get('contextLines', 50);
        this.enableAutoComplete = config.get('enableAutoComplete', true);
    }

    updateConfig(config: vscode.WorkspaceConfiguration) {
        this.debounceTime = config.get('debounceTime', 300);
        this.contextLines = config.get('contextLines', 50);
        this.enableAutoComplete = config.get('enableAutoComplete', true);
    }

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | vscode.InlineCompletionList | null> {
        // Check if auto-complete is enabled
        if (!this.enableAutoComplete && context.triggerKind === vscode.InlineCompletionTriggerKind.Automatic) {
            return null;
        }

        // Check if extension is enabled
        const config = vscode.workspace.getConfiguration('eddie-copilot');
        if (!config.get('enable', true)) {
            return null;
        }

        // Skip if already generating
        if (this.isGenerating) {
            return null;
        }

        // Get the text before and after cursor
        const prefix = this.getPrefix(document, position);
        const suffix = this.getSuffix(document, position);

        // Skip if prefix is too short or just whitespace
        if (prefix.trim().length < 3) {
            return null;
        }

        // Check cache first
        const cacheKey = this.getCacheKey(document, position);
        const cached = this.cache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp) < this.CACHE_TTL) {
            if (cached.prefix === prefix.slice(-100)) {
                return this.createCompletionItems(cached.completion, position);
            }
        }

        // Debounce for automatic triggers
        if (context.triggerKind === vscode.InlineCompletionTriggerKind.Automatic) {
            return new Promise((resolve) => {
                if (this.debounceTimer) {
                    clearTimeout(this.debounceTimer);
                }

                this.debounceTimer = setTimeout(async () => {
                    if (token.isCancellationRequested) {
                        resolve(null);
                        return;
                    }

                    const result = await this.generateCompletion(
                        document,
                        position,
                        prefix,
                        suffix,
                        token
                    );
                    resolve(result);
                }, this.debounceTime);
            });
        }

        // Direct generation for explicit triggers
        return this.generateCompletion(document, position, prefix, suffix, token);
    }

    private async generateCompletion(
        document: vscode.TextDocument,
        position: vscode.Position,
        prefix: string,
        suffix: string,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | null> {
        if (token.isCancellationRequested) {
            return null;
        }

        this.isGenerating = true;
        this.lastCompletionRequest = Date.now();

        try {
            const language = document.languageId;
            const filename = document.fileName.split(/[/\\]/).pop() || 'unknown';

            const completion = await this.ollamaClient.complete(
                prefix,
                suffix,
                language,
                filename,
                token
            );

            if (!completion || token.isCancellationRequested) {
                return null;
            }

            // Cache the result
            const cacheKey = this.getCacheKey(document, position);
            this.cache.set(cacheKey, {
                prefix: prefix.slice(-100),
                completion: completion,
                timestamp: Date.now()
            });

            // Clean old cache entries
            this.cleanCache();

            return this.createCompletionItems(completion, position);
        } catch (error) {
            console.error('Error generating completion:', error);
            return null;
        } finally {
            this.isGenerating = false;
        }
    }

    private createCompletionItems(
        completion: string,
        position: vscode.Position
    ): vscode.InlineCompletionItem[] {
        const item = new vscode.InlineCompletionItem(
            completion,
            new vscode.Range(position, position)
        );

        this.suggestions = [item];
        this.currentSuggestionIndex = 0;

        return [item];
    }

    private getPrefix(document: vscode.TextDocument, position: vscode.Position): string {
        const startLine = Math.max(0, position.line - this.contextLines);
        const startPosition = new vscode.Position(startLine, 0);
        return document.getText(new vscode.Range(startPosition, position));
    }

    private getSuffix(document: vscode.TextDocument, position: vscode.Position): string {
        const endLine = Math.min(document.lineCount - 1, position.line + this.contextLines);
        const endPosition = new vscode.Position(endLine, document.lineAt(endLine).text.length);
        return document.getText(new vscode.Range(position, endPosition));
    }

    private getCacheKey(document: vscode.TextDocument, position: vscode.Position): string {
        return `${document.uri.toString()}:${position.line}:${position.character}`;
    }

    private cleanCache() {
        const now = Date.now();
        for (const [key, value] of this.cache.entries()) {
            if ((now - value.timestamp) > this.CACHE_TTL) {
                this.cache.delete(key);
            }
        }
    }

    getNextSuggestion(): vscode.InlineCompletionItem | null {
        if (this.suggestions.length === 0) {
            return null;
        }
        this.currentSuggestionIndex = (this.currentSuggestionIndex + 1) % this.suggestions.length;
        return this.suggestions[this.currentSuggestionIndex];
    }

    getPreviousSuggestion(): vscode.InlineCompletionItem | null {
        if (this.suggestions.length === 0) {
            return null;
        }
        this.currentSuggestionIndex = (this.currentSuggestionIndex - 1 + this.suggestions.length) % this.suggestions.length;
        return this.suggestions[this.currentSuggestionIndex];
    }

    clearSuggestions() {
        this.suggestions = [];
        this.currentSuggestionIndex = 0;
    }
}
