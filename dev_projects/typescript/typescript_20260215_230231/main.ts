import { JiraClient } from 'jira-client';

class JiraIntegration {
    private client: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.client = new JiraClient({
            url: jiraUrl,
            username: username,
            password: password
        });
    }

    async fetchIssues(): Promise<any[]> {
        try {
            const issues = await this.client.searchJql('project = YOUR_PROJECT_KEY');
            return issues;
        } catch (error) {
            console.error('Error fetching issues:', error);
            throw error;
        }
    }

    async updateIssue(issueId: string, fields: any): Promise<any> {
        try {
            const updatedIssue = await this.client.updateIssue(issueId, fields);
            return updatedIssue;
        } catch (error) {
            console.error('Error updating issue:', error);
            throw error;
        }
    }

    async createIssue(fields: any): Promise<any> {
        try {
            const createdIssue = await this.client.createIssue(fields);
            return createdIssue;
        } catch (error) {
            console.error('Error creating issue:', error);
            throw error;
        }
    }
}

async function main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const integration = new JiraIntegration(jiraUrl, username, password);

    try {
        const issues = await integration.fetchIssues();
        console.log('Issues:', issues);

        // Example of updating an issue
        const issueId = 'YOUR_ISSUE_ID';
        const updatedFields = { summary: 'Updated Summary' };
        await integration.updateIssue(issueId, updatedFields);
        console.log('Issue updated successfully');

        // Example of creating a new issue
        const newIssueFields = {
            project: { key: 'YOUR_PROJECT_KEY' },
            summary: 'New Issue',
            description: 'This is a new issue created via TypeScript'
        };
        await integration.createIssue(newIssueFields);
        console.log('New issue created successfully');
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

if (require.main === module) {
    main();
}