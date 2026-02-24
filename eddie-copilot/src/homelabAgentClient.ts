/**
 * Homelab Agent Client — Integração VS Code com a API do Homelab Agent
 *
 * Comunica com o endpoint /homelab/* na API de agentes especializados (porta 8503).
 * Somente funciona em rede local (RFC 1918).
 */

import * as vscode from 'vscode';

const DEFAULT_API_URL = 'http://localhost:8503';

export interface CommandResult {
    success: boolean;
    command: string;
    stdout: string;
    stderr: string;
    exit_code: number;
    duration_ms: number;
    timestamp: string;
    error: string | null;
    category: string | null;
}

export interface ServerHealth {
    status: string;
    uptime?: string;
    memory?: string;
    disk?: string;
    cpu_load?: string;
    hostname?: string;
    kernel?: string;
    timestamp?: string;
}

export interface AuditEntry {
    timestamp: string;
    command: string;
    caller_ip: string;
    success: boolean;
    exit_code: number;
    duration_ms: number;
    blocked: boolean;
    block_reason: string | null;
}

export class HomelabAgentClient {
    private apiUrl: string;
    private timeout: number;

    constructor(config?: vscode.WorkspaceConfiguration) {
        this.apiUrl = config?.get<string>('agentsApiUrl', DEFAULT_API_URL) || DEFAULT_API_URL;
        this.timeout = 30000; // 30s
    }

    updateConfig(config: vscode.WorkspaceConfiguration): void {
        this.apiUrl = config.get<string>('agentsApiUrl', DEFAULT_API_URL) || DEFAULT_API_URL;
    }

    private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
        const url = `${this.apiUrl}${path}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            // Use globalThis.fetch (Node 18+ / VS Code runtime)
            // Fallback to node-fetch for older environments
            let fetchFn: typeof globalThis.fetch;
            if (typeof globalThis.fetch === 'function') {
                fetchFn = globalThis.fetch;
            } else {
                // eslint-disable-next-line @typescript-eslint/no-var-requires
                const mod = require('node-fetch');
                fetchFn = mod.default || mod;
            }

            const response = await fetchFn(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options?.headers,
                },
            });

            if (!response.ok) {
                const text = await response.text();
                throw new Error(`HTTP ${response.status}: ${text}`);
            }

            return await response.json() as T;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    // ---- Health ----

    async isAvailable(): Promise<boolean> {
        try {
            const data = await this.fetch<{ status: string }>('/homelab/health');
            return data.status === 'online';
        } catch {
            return false;
        }
    }

    async getServerHealth(): Promise<ServerHealth | null> {
        try {
            const data = await this.fetch<{ status: string; data: ServerHealth }>('/homelab/server-health');
            return data.data;
        } catch {
            return null;
        }
    }

    // ---- Execute Commands ----

    async execute(command: string, timeout?: number): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/execute', {
            method: 'POST',
            body: JSON.stringify({ command, timeout: timeout || 30 }),
        });
    }

    async validateCommand(command: string): Promise<{ command: string; allowed: boolean; reason: string | null; category: string | null }> {
        return this.fetch('/homelab/validate-command', {
            method: 'POST',
            body: JSON.stringify({ command }),
        });
    }

    // ---- Docker ----

    async dockerPs(all = false): Promise<CommandResult> {
        return this.fetch<CommandResult>(`/homelab/docker/ps?all=${all}`);
    }

    async dockerLogs(container: string, tail = 50): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/docker/logs', {
            method: 'POST',
            body: JSON.stringify({ container, tail }),
        });
    }

    async dockerStats(): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/docker/stats');
    }

    async dockerRestart(container: string): Promise<CommandResult> {
        return this.fetch<CommandResult>(`/homelab/docker/restart?container=${encodeURIComponent(container)}`, {
            method: 'POST',
        });
    }

    // ---- Systemd ----

    async systemdStatus(service: string): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/systemd/status', {
            method: 'POST',
            body: JSON.stringify({ service }),
        });
    }

    async systemdRestart(service: string): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/systemd/restart', {
            method: 'POST',
            body: JSON.stringify({ service }),
        });
    }

    async systemdList(state = 'running'): Promise<CommandResult> {
        return this.fetch<CommandResult>(`/homelab/systemd/list?state=${state}`);
    }

    async systemdLogs(service: string, lines = 50): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/systemd/logs', {
            method: 'POST',
            body: JSON.stringify({ service, lines }),
        });
    }

    // ---- System Info ----

    async diskUsage(path = '/'): Promise<CommandResult> {
        return this.fetch<CommandResult>(`/homelab/system/disk?path=${encodeURIComponent(path)}`);
    }

    async memoryUsage(): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/system/memory');
    }

    async cpuInfo(): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/system/cpu');
    }

    async networkInfo(): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/system/network');
    }

    async listeningPorts(): Promise<CommandResult> {
        return this.fetch<CommandResult>('/homelab/system/ports');
    }

    // ---- Audit ----

    async getAuditLog(lastN = 50): Promise<{ entries: AuditEntry[]; total: number }> {
        return this.fetch(`/homelab/audit?last_n=${lastN}`);
    }

    async getAllowedCommands(): Promise<Record<string, string[]>> {
        return this.fetch('/homelab/allowed-commands');
    }
}
