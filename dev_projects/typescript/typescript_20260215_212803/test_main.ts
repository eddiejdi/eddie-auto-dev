import { AgentConfig } from './agent-config';
import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from '../src/typescript-agent';

describe('TypeScriptAgent', () => {
    describe('trackActivity', () => {
        it('should track activity successfully with valid values', async () => {
            const agentConfig = new AgentConfig({
                server: 'https://your-jira-server.com',
                username: 'your-username',
                password: 'your-password',
                issueKey: 'YOUR-ISSUE-KEY'
            });

            const agent = new TypeScriptAgent(agentConfig);
            await agent.trackActivity('New TypeScript project started.');
        });

        it('should handle errors with invalid values', async () => {
            const agentConfig = new AgentConfig({
                server: 'https://your-jira-server.com',
                username: 'your-username',
                password: 'your-password',
                issueKey: 'YOUR-ISSUE-KEY'
            });

            const agent = new TypeScriptAgent(agentConfig);
            await expect(agent.trackActivity('')).rejects.toThrowError();
        });
    });

    describe('main', () => {
        it('should track activity successfully with valid values', async () => {
            const agentConfig = new AgentConfig({
                server: 'https://your-jira-server.com',
                username: 'your-username',
                password: 'your-password',
                issueKey: 'YOUR-ISSUE-KEY'
            });

            const agent = new TypeScriptAgent(agentConfig);
            await agent.main();
        });
    });
});