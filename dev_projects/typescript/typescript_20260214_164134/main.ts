import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

class TypeScriptAgent {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            auth: { basic: { username, password } }
        });
    }

    async createIssue(title: string, description: string): Promise<Issue> {
        const issueData = {
            fields: {
                project: { key: 'YOUR_PROJECT_KEY' },
                summary: title,
                description: description,
                issuetype: { name: 'Bug' }
            }
        };

        try {
            const createdIssue = await this.jiraClient.createIssue(issueData);
            console.log(`Created issue: ${createdIssue.key}`);
            return createdIssue;
        } catch (error) {
            console.error('Error creating issue:', error);
            throw error;
        }
    }

    async updateIssue(issueKey: string, title?: string, description?: string): Promise<Issue> {
        const issueData = {};

        if (title) {
            issueData.fields.summary = title;
        }

        if (description) {
            issueData.fields.description = description;
        }

        try {
            const updatedIssue = await this.jiraClient.updateIssue(issueKey, issueData);
            console.log(`Updated issue: ${updatedIssue.key}`);
            return updatedIssue;
        } catch (error) {
            console.error('Error updating issue:', error);
            throw error;
        }
    }

    async closeIssue(issueKey: string): Promise<void> {
        try {
            await this.jiraClient.updateIssue(issueKey, { fields: { status: { name: 'Closed' } } });
            console.log(`Closed issue: ${issueKey}`);
        } catch (error) {
            console.error('Error closing issue:', error);
        }
    }

    async deleteIssue(issueKey: string): Promise<void> {
        try {
            await this.jiraClient.deleteIssue(issueKey);
            console.log(`Deleted issue: ${issueKey}`);
        } catch (error) {
            console.error('Error deleting issue:', error);
        }
    }
}

async function main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new TypeScriptAgent(jiraUrl, username, password);

    try {
        await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.');
        await agent.updateIssue('TC001', 'Updated title', 'Updated description');
        await agent.closeIssue('TC001');
        await agent.deleteIssue('TC001');
    } catch (error) {
        console.error('Error during operations:', error);
    }
}

if (require.main === module) {
    main();
}