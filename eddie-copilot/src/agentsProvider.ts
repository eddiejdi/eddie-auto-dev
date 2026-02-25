import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class AgentsProvider {
    private agentsApiUrl: string;
    private knownAgents: string[] = [];
    private config: vscode.WorkspaceConfiguration;

    constructor(config: vscode.WorkspaceConfiguration) {
        this.config = config;
        this.agentsApiUrl = config.get('agentsApiUrl', 'http://localhost:8503');
        this.knownAgents = config.get('knownAgents', []);
    }

    async fetchAgents(): Promise<string[]> {
        try {
            const url = `${this.agentsApiUrl}/agents`;
            let fetchFn: typeof globalThis.fetch;
            if (typeof globalThis.fetch === 'function') {
                fetchFn = globalThis.fetch;
            } else {
                // eslint-disable-next-line @typescript-eslint/no-var-requires
                const mod = require('node-fetch');
                fetchFn = mod.default || mod;
            }
            const resp = await fetchFn(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
            if (!resp.ok) throw new Error(`API error: ${resp.status}`);
            const data = await resp.json();
            const langs = data.available_languages || data.available || [];
            if (Array.isArray(langs) && langs.length > 0) {
                this.knownAgents = langs;
                return langs;
            }
        } catch (e) {
            // fallback
        }
        return this.loadLocalAgents();
    }

    loadLocalAgents(): string[] {
        // Try to load known_agents.json from eddie-copilot folder
        try {
            const extPath = vscode.extensions.getExtension('eddie.eddie-copilot')?.extensionPath;
            if (extPath) {
                const filePath = path.join(extPath, 'known_agents.json');
                if (fs.existsSync(filePath)) {
                    const content = fs.readFileSync(filePath, 'utf-8');
                    const arr = JSON.parse(content);
                    if (Array.isArray(arr)) {
                        this.knownAgents = arr;
                        return arr;
                    }
                }
            }
        } catch (e) {
            // fallback
        }
        // fallback to config
        return this.knownAgents;
    }

    getAgents(): string[] {
        return this.knownAgents;
    }
}
