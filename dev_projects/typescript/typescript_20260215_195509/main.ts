import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraIntegration {
    private jiraClient: JiraClient;
    private agent: Agent;

    constructor(jiraHost: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            host: jiraHost,
            auth: { username, password }
        });

        this.agent = new Agent(this.jiraClient);
    }

    async startTracking(issueKey: string): Promise<void> {
        try {
            await this.agent.startTracking(issueKey);
            console.log(`Activity tracking started for issue ${issueKey}`);
        } catch (error) {
            console.error('Error starting activity tracking:', error);
        }
    }

    async stopTracking(issueKey: string): Promise<void> {
        try {
            await this.agent.stopTracking(issueKey);
            console.log(`Activity tracking stopped for issue ${issueKey}`);
        } catch (error) {
            console.error('Error stopping activity tracking:', error);
        }
    }
}

// Example usage
async function main() {
    const jiraHost = 'https://your-jira-host.com';
    const username = 'your-username';
    const password = 'your-password';

    const integration = new JiraIntegration(jiraHost, username, password);

    try {
        await integration.startTracking('ABC-123');
        // Simulate some activity
        await integration.stopTracking('ABC-123');
    } catch (error) {
        console.error('Error integrating with Jira:', error);
    }
}

if (require.main === module) {
    main();
}