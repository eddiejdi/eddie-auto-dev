import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraTypeScriptAgent {
    private client: JiraClient;
    private agent: Agent;

    constructor(jiraUrl: string, username: string, password: string) {
        this.client = new JiraClient({
            url: jiraUrl,
            username: username,
            password: password
        });
        this.agent = new Agent(this.client);
    }

    async startTrackingIssue(issueKey: string): Promise<void> {
        try {
            await this.agent.startTrackingIssue(issueKey);
            console.log(`Tracking issue ${issueKey} started.`);
        } catch (error) {
            console.error('Error starting tracking issue:', error);
        }
    }

    async stopTrackingIssue(issueKey: string): Promise<void> {
        try {
            await this.agent.stopTrackingIssue(issueKey);
            console.log(`Tracking issue ${issueKey} stopped.`);
        } catch (error) {
            console.error('Error stopping tracking issue:', error);
        }
    }

    async updateIssueStatus(issueKey: string, status: string): Promise<void> {
        try {
            await this.client.issue.update({
                fields: {
                    status: {
                        name: status
                    }
                },
                id: issueKey
            });
            console.log(`Updated status of issue ${issueKey} to ${status}.`);
        } catch (error) {
            console.error('Error updating issue status:', error);
        }
    }

    async main(): Promise<void> {
        const jiraUrl = 'https://your-jira-instance.atlassian.net';
        const username = 'your-username';
        const password = 'your-password';

        const agent = new JiraTypeScriptAgent(jiraUrl, username, password);

        try {
            await agent.startTrackingIssue('ABC-123');
            await agent.updateIssueStatus('ABC-123', 'In Progress');
            await agent.stopTrackingIssue('ABC-123');
        } catch (error) {
            console.error('Main function failed:', error);
        }
    }

    static main(): void {
        const jiraUrl = 'https://your-jira-instance.atlassian.net';
        const username = 'your-username';
        const password = 'your-password';

        new JiraTypeScriptAgent(jiraUrl, username, password).main();
    }
}

if (require.main === module) {
    JiraTypeScriptAgent.main();
}