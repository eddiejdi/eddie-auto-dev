import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

class TypeScriptAgent {
    private client: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.client = new JiraClient({
            url: jiraUrl,
            auth: {
                username,
                password
            }
        });
    }

    async createIssue(title: string, description: string): Promise<Issue> {
        try {
            const issueData = {
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description
                }
            };

            return await this.client.createIssue(issueData);
        } catch (error) {
            throw new Error('Failed to create issue:', error);
        }
    }

    async updateIssue(issueId: string, title?: string, description?: string): Promise<Issue> {
        try {
            const issueData = {};

            if (title) {
                issueData.fields.summary = title;
            }

            if (description) {
                issueData.fields.description = description;
            }

            return await this.client.updateIssue(issueId, issueData);
        } catch (error) {
            throw new Error('Failed to update issue:', error);
        }
    }

    async deleteIssue(issueId: string): Promise<void> {
        try {
            await this.client.deleteIssue(issueId);
        } catch (error) {
            throw new Error('Failed to delete issue:', error);
        }
    }
}

// Example usage
(async () => {
    const client = new TypeScriptAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
    );

    try {
        const issue = await client.createIssue('TypeScript Integration', 'This is a test issue for TypeScript integration.');
        console.log('Created issue:', issue);

        // Update the issue
        await client.updateIssue(issue.id, 'Updated title', 'Updated description');
        console.log('Updated issue:', issue);

        // Delete the issue
        await client.deleteIssue(issue.id);
        console.log('Deleted issue.');
    } catch (error) {
        console.error(error);
    }
})();