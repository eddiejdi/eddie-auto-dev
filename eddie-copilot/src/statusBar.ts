import * as vscode from 'vscode';

export class StatusBarManager implements vscode.Disposable {
    private statusBarItem: vscode.StatusBarItem;
    private isConnected = false;
    private isEnabled = true;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'eddie-copilot.openChat';
        this.updateStatusBar();
        this.statusBarItem.show();
    }

    private updateStatusBar() {
        if (!this.isEnabled) {
            this.statusBarItem.text = '$(circle-slash) Eddie Copilot';
            this.statusBarItem.tooltip = 'Eddie Copilot is disabled. Click to open chat.';
            this.statusBarItem.backgroundColor = undefined;
        } else if (this.isConnected) {
            this.statusBarItem.text = '$(sparkle) Eddie Copilot';
            this.statusBarItem.tooltip = 'Eddie Copilot is ready. Click to open chat.';
            this.statusBarItem.backgroundColor = undefined;
        } else {
            this.statusBarItem.text = '$(warning) Eddie Copilot';
            this.statusBarItem.tooltip = 'Eddie Copilot: Not connected to Ollama. Click to open chat.';
            this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }

    setConnected() {
        this.isConnected = true;
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
        this.statusBarItem.text = '$(loading~spin) Eddie Copilot';
        this.statusBarItem.tooltip = 'Eddie Copilot is generating...';
    }

    clearGenerating() {
        this.updateStatusBar();
    }

    dispose() {
        this.statusBarItem.dispose();
    }
}
