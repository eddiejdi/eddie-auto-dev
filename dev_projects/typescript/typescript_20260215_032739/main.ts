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
                    summary: title,
                    description: description
                }
            });
            console.log('Issue created successfully');
        } catch (error) {
            console.error('Error creating issue:', error);
        }
    }

    async updateIssue(issueId: string, title: string, description: string): Promise<void> {
        try {
            await this.jiraClient.updateIssue({
                issueId,
                fields: {
                    summary: title,
                    description: description
                }
            });
            console.log('Issue updated successfully');
        } catch (error) {
            console.error('Error updating issue:', error);
        }
    }

    async closeIssue(issueId: string): Promise<void> {
        try {
            await this.jiraClient.updateIssue({
                issueId,
                fields: {
                    status: 'Closed'
                }
            });
            console.log('Issue closed successfully');
        } catch (error) {
            console.error('Error closing issue:', error);
        }
    }

    async getIssues(): Promise<Array<any>> {
        try {
            const issues = await this.jiraClient.getIssues();
            return issues;
        } catch (error) {
            console.error('Error fetching issues:', error);
            return [];
        }
    }
}

async function main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new TypeScriptAgent(jiraUrl, username, password);

    try {
        await agent.createIssue('New TypeScript Issue', 'This is a test issue created by TypeScript Agent');
        console.log('Created issue successfully');

        // Update the issue
        await agent.updateIssue('1234567890', 'Updated TypeScript Issue', 'This is an updated test issue created by TypeScript Agent');

        // Close the issue
        await agent.closeIssue('1234567890');

        // Get all issues
        const issues = await agent.getIssues();
        console.log('Issues:', issues);
    } catch (error) {
        console.error('Error executing operations:', error);
    }
}

if (require.main === module) {
    main();
}