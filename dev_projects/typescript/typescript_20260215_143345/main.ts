import { JiraClient } from 'jira-client';

class TypeScriptAgent {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            username: username,
            password: password
        });
    }

    async createIssue(title: string, description: string): Promise<void> {
        try {
            await this.jiraClient.createIssue({
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description
                }
            });
            console.log('Issue created successfully');
        } catch (error) {
            console.error('Error creating issue:', error);
        }
    }

    async updateIssue(issueKey: string, title?: string, description?: string): Promise<void> {
        try {
            const updatedFields = {};
            if (title) updatedFields.summary = title;
            if (description) updatedFields.description = description;

            await this.jiraClient.updateIssue({
                issueKey,
                fields: updatedFields
            });
            console.log('Issue updated successfully');
        } catch (error) {
            console.error('Error updating issue:', error);
        }
    }

    async deleteIssue(issueKey: string): Promise<void> {
        try {
            await this.jiraClient.deleteIssue({
                issueKey
            });
            console.log('Issue deleted successfully');
        } catch (error) {
            console.error('Error deleting issue:', error);
        }
    }
}

// Example usage in a CLI application
if (require.main === module) {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new TypeScriptAgent(jiraUrl, username, password);

    async function main() {
        try {
            await agent.createIssue('Task 1', 'This is a test task');
            await agent.updateIssue('TASK-1', 'Updated task title', 'Updated task description');
            await agent.deleteIssue('TASK-1');
        } catch (error) {
            console.error(error);
        }
    }

    main();
}