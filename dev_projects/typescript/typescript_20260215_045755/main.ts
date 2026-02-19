import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

class TypeScriptAgent {
    private client: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.client = new JiraClient({
            url: jiraUrl,
            username: username,
            password: password
        });
    }

    async createIssue(title: string, description: string): Promise<Issue> {
        try {
            const issue = await this.client.createIssue({
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description,
                    issuetype: { name: 'Bug' }
                }
            });

            console.log('Issue created:', issue);
            return issue;
        } catch (error) {
            throw new Error(`Failed to create issue: ${error.message}`);
        }
    }

    async updateIssue(issueId: string, title?: string, description?: string): Promise<Issue> {
        try {
            const updatedFields = {};
            if (title) updatedFields.summary = title;
            if (description) updatedFields.description = description;

            const issue = await this.client.updateIssue({
                id: issueId,
                fields: updatedFields
            });

            console.log('Issue updated:', issue);
            return issue;
        } catch (error) {
            throw new Error(`Failed to update issue: ${error.message}`);
        }
    }

    async deleteIssue(issueId: string): Promise<void> {
        try {
            await this.client.deleteIssue({
                id: issueId
            });

            console.log('Issue deleted');
        } catch (error) {
            throw new Error(`Failed to delete issue: ${error.message}`);
        }
    }
}

// Example usage:
const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

async function main() {
    try {
        const issue = await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for TypeScript Agent integration.');
        console.log('Created issue:', issue);

        await agent.updateIssue(issue.id, 'Updated Title', 'Updated Description');
        console.log('Updated issue:', issue);

        await agent.deleteIssue(issue.id);
        console.log('Deleted issue');
    } catch (error) {
        console.error(error.message);
    }
}

if (require.main === module) {
    main();
}