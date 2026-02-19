import { JiraClient } from 'jira-client';
import { expect } from 'chai';

class TypeScriptAgent {
    private client: JiraClient;

    constructor(token: string) {
        this.client = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            auth: token,
        });
    }

    async trackActivity(issueKey: string, activityDescription: string): Promise<void> {
        try {
            await this.client.issue.update(issueKey, {
                fields: {
                    description: activityDescription,
                },
            });

            console.log(`Activity tracked for issue ${issueKey}`);
        } catch (error) {
            console.error('Error tracking activity:', error);
        }
    }

    async getIssueDetails(issueKey: string): Promise<any> {
        try {
            const issue = await this.client.issue.get(issueKey);

            return issue;
        } catch (error) {
            console.error('Error getting issue details:', error);
            throw error;
        }
    }
}

async function main() {
    const token = 'your-jira-token';
    const agent = new TypeScriptAgent(token);

    try {
        await agent.trackActivity('ABC-123', 'Updated the description of the issue');
        const issueDetails = await agent.getIssueDetails('ABC-123');
        console.log(issueDetails);
    } catch (error) {
        console.error('Main process failed:', error);
    }
}

if (require.main === module) {
    main();
}