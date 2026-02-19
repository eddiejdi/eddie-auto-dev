import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/model/issue';

class TypeScriptAgent {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            auth: {
                username: username,
                password: password
            }
        });
    }

    async createIssue(title: string, description: string): Promise<Issue> {
        try {
            const issueData = {
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description,
                    issuetype: { name: 'Bug' }
                }
            };

            const issue = await this.jiraClient.createIssue(issueData);
            return issue;
        } catch (error) {
            console.error('Error creating issue:', error);
            throw error;
        }
    }

    async updateIssue(issueId: string, title?: string, description?: string): Promise<Issue> {
        try {
            const issueData = {};

            if (title) issueData.fields.summary = title;
            if (description) issueData.fields.description = description;

            const updatedIssue = await this.jiraClient.updateIssue(issueId, issueData);
            return updatedIssue;
        } catch (error) {
            console.error('Error updating issue:', error);
            throw error;
        }
    }

    async deleteIssue(issueId: string): Promise<void> {
        try {
            await this.jiraClient.deleteIssue(issueId);
        } catch (error) {
            console.error('Error deleting issue:', error);
        }
    }
}

// Example usage
const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

(async () => {
    try {
        const issue = await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.');
        console.log('Created issue:', issue);

        // Update the issue
        await agent.updateIssue(issue.id, 'Updated TypeScript Agent Integration', 'This is an updated test issue.');

        // Delete the issue
        await agent.deleteIssue(issue.id);
        console.log('Deleted issue successfully.');
    } catch (error) {
        console.error(error);
    }
})();