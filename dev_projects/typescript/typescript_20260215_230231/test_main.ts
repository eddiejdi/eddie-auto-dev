import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('JiraIntegration', () => {
    let integration: JiraIntegration;

    beforeEach(() => {
        const jiraUrl = 'https://your-jira-instance.atlassian.net';
        const username = 'your-username';
        const password = 'your-password';
        integration = new JiraIntegration(jiraUrl, username, password);
    });

    describe('fetchIssues', () => {
        it('should fetch issues successfully', async () => {
            // Simulate a successful response from the Jira API
            const mockIssues = [
                { key: 'ABC123' },
                { key: 'XYZ456' }
            ];
            integration.client.searchJql.mockResolvedValue(mockIssues);

            const issues = await integration.fetchIssues();
            expect(issues).to.have.lengthOf(2);
        });

        it('should throw an error if the Jira API call fails', async () => {
            // Simulate a failed response from the Jira API
            integration.client.searchJql.mockRejectedValue(new Error('Failed to fetch issues'));

            await expect(integration.fetchIssues()).to.be.rejected;
        });
    });

    describe('updateIssue', () => {
        it('should update an issue successfully', async () => {
            // Simulate a successful response from the Jira API
            const mockUpdatedIssue = { key: 'ABC123' };
            integration.client.updateIssue.mockResolvedValue(mockUpdatedIssue);

            const issueId = 'YOUR_ISSUE_ID';
            const updatedFields = { summary: 'Updated Summary' };
            await integration.updateIssue(issueId, updatedFields);
            expect(integration.client.updateIssue).to.have.be.calledWith(issueId, updatedFields);
        });

        it('should throw an error if the Jira API call fails', async () => {
            // Simulate a failed response from the Jira API
            integration.client.updateIssue.mockRejectedValue(new Error('Failed to update issue'));

            await expect(integration.updateIssue('YOUR_ISSUE_ID', { summary: 'Updated Summary' })).to.be.rejected;
        });
    });

    describe('createIssue', () => {
        it('should create an issue successfully', async () => {
            // Simulate a successful response from the Jira API
            const mockCreatedIssue = { key: 'ABC123' };
            integration.client.createIssue.mockResolvedValue(mockCreatedIssue);

            const newIssueFields = {
                project: { key: 'YOUR_PROJECT_KEY' },
                summary: 'New Issue',
                description: 'This is a new issue created via TypeScript'
            };
            await integration.createIssue(newIssueFields);
            expect(integration.client.createIssue).to.have.be.calledWith(newIssueFields);
        });

        it('should throw an error if the Jira API call fails', async () => {
            // Simulate a failed response from the Jira API
            integration.client.createIssue.mockRejectedValue(new Error('Failed to create issue'));

            await expect(integration.createIssue({ project: { key: 'YOUR_PROJECT_KEY' }, summary: 'New Issue', description: 'This is a new issue created via TypeScript' })).to.be.rejected;
        });
    });
});