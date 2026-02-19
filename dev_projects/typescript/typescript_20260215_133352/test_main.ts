import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('JiraAgent', () => {
    let agent: Agent;

    beforeEach(() => {
        agent = new Agent();
    });

    afterEach(() => {
        // Cleanup code if needed
    });

    describe('createIssue', () => {
        it('should create an issue with valid fields', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await agent.createIssue('Test Issue', 'This is a test issue created by TypeScript Agent.');
        });

        it('should throw an error if the description is empty', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await expect(agent.createIssue('Test Issue', '')).rejects.toThrowError('Description cannot be empty');
        });
    });

    describe('updateIssue', () => {
        it('should update an issue with valid fields', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await agent.updateIssue('YOUR_ISSUE_ID', 'Updated issue title', 'Updated issue description');
        });

        it('should throw an error if the summary is empty', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await expect(agent.updateIssue('YOUR_ISSUE_ID', '', 'Updated issue description')).rejects.toThrowError('Summary cannot be empty');
        });
    });

    describe('deleteIssue', () => {
        it('should delete an issue with valid fields', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await agent.deleteIssue('YOUR_ISSUE_ID');
        });

        it('should throw an error if the issue ID is invalid', async () => {
            const token = 'YOUR_JIRA_TOKEN';
            const baseUrl = 'https://your-jira-instance.atlassian.net';

            const client = new JiraClient({
                auth: token,
                url: baseUrl,
                strictSSL: false
            });

            await expect(agent.deleteIssue('INVALID_ISSUE_ID')).rejects.toThrowError('Invalid issue ID');
        });
    });
});