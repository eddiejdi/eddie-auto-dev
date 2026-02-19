import { JiraClient } from 'jira-client';
import { AgentConfig } from './agent-config';

class TypeScriptAgent {
    private jiraClient: JiraClient;
    private agentConfig: AgentConfig;

    constructor(agentConfig: AgentConfig) {
        this.agentConfig = agentConfig;
        this.jiraClient = new JiraClient({
            server: agentConfig.server,
            username: agentConfig.username,
            password: agentConfig.password
        });
    }

    async trackActivity(activity: string): Promise<void> {
        try {
            await this.jiraClient.addComment(this.agentConfig.issueKey, activity);
            console.log(`Activity tracked successfully in Jira.`);
        } catch (error) {
            console.error(`Error tracking activity in Jira:`, error);
        }
    }

    async main(): Promise<void> {
        const activity = 'New TypeScript project started.';
        await this.trackActivity(activity);
    }
}

// Example usage:
const agentConfig = new AgentConfig({
    server: 'https://your-jira-server.com',
    username: 'your-username',
    password: 'your-password',
    issueKey: 'YOUR-ISSUE-KEY'
});

const agent = new TypeScriptAgent(agentConfig);
agent.main();