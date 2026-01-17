import * as vscode from 'vscode';

export class StatusBarManager implements vscode.Disposable {
    private statusBarItem: vscode.StatusBarItem;
    private isConnected = false;
    private isEnabled = true;
    private isRemoteConnected = false;
    private localModel = '';
    private remoteModel = '';

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'eddie-copilot.showStatus';
        this.updateStatusBar();
        this.statusBarItem.show();
    }

    private updateStatusBar() {
        if (!this.isEnabled) {
            this.statusBarItem.text = '$(circle-slash) Eddie';
            this.statusBarItem.tooltip = 'Eddie Copilot desabilitado. Clique para status.';
            this.statusBarItem.backgroundColor = undefined;
        } else if (this.isConnected && this.isRemoteConnected) {
            this.statusBarItem.text = '$(sparkle) Eddie [L+R]';
            this.statusBarItem.tooltip = `Eddie Copilot conectado!\n\nLocal: ${this.localModel}\nRemoto: ${this.remoteModel}\n\nClique para detalhes.`;
            this.statusBarItem.backgroundColor = undefined;
        } else if (this.isConnected) {
            this.statusBarItem.text = '$(sparkle) Eddie [L]';
            this.statusBarItem.tooltip = `Eddie Copilot (modo local)\n\nModelo: ${this.localModel}\n\nClique para configurar remoto.`;
            this.statusBarItem.backgroundColor = undefined;
        } else {
            this.statusBarItem.text = '$(warning) Eddie';
            this.statusBarItem.tooltip = 'Eddie Copilot: Sem conexão. Clique para verificar.';
            this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }

    setConnected(localModel?: string) {
        this.isConnected = true;
        if (localModel) {
            this.localModel = localModel;
        }
        this.updateStatusBar();
    }

    setRemoteConnected(remoteModel?: string) {
        this.isRemoteConnected = true;
        if (remoteModel) {
            this.remoteModel = remoteModel;
        }
        this.updateStatusBar();
    }

    setRemoteDisconnected() {
        this.isRemoteConnected = false;
        this.updateStatusBar();
    }

    setDisconnected() {
        this.isConnected = false;
        this.updateStatusBar();
    }

    setEnabled() {
        this.isEnabled = true;
        this.updateStatusBar();
    }

    setDisabled() {
        this.isEnabled = false;
        this.updateStatusBar();
    }

    setGenerating() {
        this.statusBarItem.text = '$(loading~spin) Eddie';
        this.statusBarItem.tooltip = 'Eddie Copilot gerando...';
    }

    clearGenerating() {
        this.updateStatusBar();
    }

    dispose() {
        this.statusBarItem.dispose();
    }
}
