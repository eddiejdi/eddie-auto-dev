import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraAgent {
    private client: JiraClient;

    constructor(token: string, baseUrl: string) {
        this.client = new JiraClient({
            auth: token,
            url: baseUrl,
            strictSSL: false
        });
    }

    async createIssue(title: string, description: string): Promise<void> {
        try {
            await this.client.createIssue({
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description,
                    issuetype: { name: 'Bug' }
                }
            });
            console.log('Issue created successfully');
        } catch (error) {
            console.error('Error creating issue:', error);
        }
    }

    async updateIssue(issueId: string, title?: string, description?: string): Promise<void> {
        try {
            await this.client.updateIssue({
                fields: {
                    summary: title,
                    description: description
                },
                issueKey: issueId
            });
            console.log('Issue updated successfully');
        } catch (error) {
            console.error('Error updating issue:', error);
        }
    }

    async deleteIssue(issueId: string): Promise<void> {
        try {
            await this.client.deleteIssue({
                issueKey: issueId
            });
            console.log('Issue deleted successfully');
        } catch (error) {
            console.error('Error deleting issue:', error);
        }
    }
}

async function main() {
    const token = 'YOUR_JIRA_TOKEN';
    const baseUrl = 'https://your-jira-instance.atlassian.net';

    const agent = new JiraAgent(token, baseUrl);

    try {
        await agent.createIssue('Test Issue', 'This is a test issue created by TypeScript Agent.');
        console.log('Created issue');

        await agent.updateIssue('YOUR_ISSUE_ID', 'Updated issue title', 'Updated issue description');
        console.log('Updated issue');

        await agent.deleteIssue('YOUR_ISSUE_ID');
        console.log('Deleted issue');
    } catch (error) {
        console.error('Error:', error);
    }
}

if (require.main === module) {
    main();
}