import { JiraClient } from 'jira-client';
import { Agent } from './agent';

class TypeScriptAgent extends Agent {
    constructor(private jiraClient: JiraClient) {
        super(jiraClient);
    }

    async trackActivity(issueKey: string, activityDescription: string): Promise<void> {
        try {
            await this.jiraClient.createIssueComment({
                issueKey,
                body: activityDescription
            });
            console.log(`Activity tracked for issue ${issueKey}`);
        } catch (error) {
            console.error('Error tracking activity:', error);
        }
    }

    async getIssues(): Promise<string[]> {
        try {
            const issues = await this.jiraClient.getIssues();
            return issues.map(issue => issue.key);
        } catch (error) {
            console.error('Error fetching issues:', error);
            return [];
        }
    }
}

// Example usage
async function main() {
    const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
    });

    const agent = new TypeScriptAgent(jiraClient);

    await agent.trackActivity('ABC-123', 'This is a test activity');
    const issues = await agent.getIssues();
    console.log('Issues:', issues);
}

if (require.main === module) {
    main().catch(error => console.error(error));
}