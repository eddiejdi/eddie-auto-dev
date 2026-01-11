import * as vscode from 'vscode';
import { OllamaClient } from './ollamaClient';

export class CodeActionProvider implements vscode.CodeActionProvider {
    public static readonly providedCodeActionKinds = [
        vscode.CodeActionKind.QuickFix,
        vscode.CodeActionKind.Refactor
    ];

    constructor(private ollamaClient: OllamaClient) {}

    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext,
        token: vscode.CancellationToken
    ): vscode.CodeAction[] | undefined {
        // Only provide actions if there's a selection
        if (range.isEmpty) {
            return undefined;
        }

        const actions: vscode.CodeAction[] = [];

        // Explain Code action
        const explainAction = new vscode.CodeAction(
            '$(lightbulb) Eddie: Explain this code',
            vscode.CodeActionKind.Empty
        );
        explainAction.command = {
            command: 'eddie-copilot.explainCode',
            title: 'Explain Code'
        };
        actions.push(explainAction);

        // Fix Code action
        const fixAction = new vscode.CodeAction(
            '$(wrench) Eddie: Fix this code',
            vscode.CodeActionKind.QuickFix
        );
        fixAction.command = {
            command: 'eddie-copilot.fixCode',
            title: 'Fix Code'
        };
        actions.push(fixAction);

        // Generate Tests action
        const testAction = new vscode.CodeAction(
            '$(beaker) Eddie: Generate tests',
            vscode.CodeActionKind.Empty
        );
        testAction.command = {
            command: 'eddie-copilot.generateTests',
            title: 'Generate Tests'
        };
        actions.push(testAction);

        // Add Documentation action
        const docAction = new vscode.CodeAction(
            '$(book) Eddie: Add documentation',
            vscode.CodeActionKind.Empty
        );
        docAction.command = {
            command: 'eddie-copilot.addDocumentation',
            title: 'Add Documentation'
        };
        actions.push(docAction);

        // Refactor Code action
        const refactorAction = new vscode.CodeAction(
            '$(edit) Eddie: Refactor code',
            vscode.CodeActionKind.Refactor
        );
        refactorAction.command = {
            command: 'eddie-copilot.refactorCode',
            title: 'Refactor Code'
        };
        actions.push(refactorAction);

        return actions;
    }
}
