import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

class JiraIntegration {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            auth: { username, password }
        });
    }

    async fetchIssues(): Promise<Issue[]> {
        try {
            const issues = await this.jiraClient.search({ jql: 'project = MyProject' });
            return issues;
        } catch (error) {
            console.error('Error fetching issues:', error);
            throw error;
        }
    }

    async createIssue(title: string, description: string): Promise<Issue> {
        try {
            const issue = await this.jiraClient.createIssue({
                fields: {
                    project: { key: 'MyProject' },
                    summary: title,
                    description: description
                }
            });
            return issue;
        } catch (error) {
            console.error('Error creating issue:', error);
            throw error;
        }
    }

    async updateIssue(issueId: string, title: string, description: string): Promise<Issue> {
        try {
            const updatedIssue = await this.jiraClient.updateIssue({
                issueId,
                fields: {
                    summary: title,
                    description: description
                }
            });
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

async function main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const integration = new JiraIntegration(jiraUrl, username, password);

    try {
        const issues = await integration.fetchIssues();
        console.log('Fetched Issues:', issues);

        const createdIssue = await integration.createIssue('New Task', 'This is a new task description.');
        console.log('Created Issue:', createdIssue);

        const updatedIssue = await integration.updateIssue(createdIssue.id, 'Updated Task', 'This is an updated task description.');
        console.log('Updated Issue:', updatedIssue);

        await integration.deleteIssue(updatedIssue.id);
        console.log('Deleted Issue');
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

if (require.main === module) {
    main();
}