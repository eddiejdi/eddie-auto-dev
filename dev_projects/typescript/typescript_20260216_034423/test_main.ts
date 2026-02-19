import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

describe('JiraIntegration', () => {
    let integration: JiraIntegration;

    beforeEach(() => {
        integration = new JiraIntegration('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
    });

    describe('fetchIssues', () => {
        it('should return issues when successful', async () => {
            const mockIssues = [
                { id: 1, key: 'ABC-123' },
                { id: 2, key: 'XYZ-456' }
            ];
            jest.spyOn(integration.jiraClient.search, 'apply').mockResolvedValue(mockIssues);

            const issues = await integration.fetchIssues();
            expect(issues).toEqual(mockIssues);
        });

        it('should throw an error if search fails', async () => {
            jest.spyOn(integration.jiraClient.search, 'apply').mockRejectedValue(new Error('Search failed'));

            try {
                await integration.fetchIssues();
            } catch (error) {
                expect(error.message).toBe('Error fetching issues: Search failed');
            }
        });
    });

    describe('createIssue', () => {
        it('should create an issue when successful', async () => {
            const mockIssue = { id: 1, key: 'ABC-123' };
            jest.spyOn(integration.jiraClient.createIssue, 'apply').mockResolvedValue(mockIssue);

            const createdIssue = await integration.createIssue('New Task', 'This is a new task description.');
            expect(createdIssue).toEqual(mockIssue);
        });

        it('should throw an error if creation fails', async () => {
            jest.spyOn(integration.jiraClient.createIssue, 'apply').mockRejectedValue(new Error('Creation failed'));

            try {
                await integration.createIssue('New Task', 'This is a new task description.');
            } catch (error) {
                expect(error.message).toBe('Error creating issue: Creation failed');
            }
        });
    });

    describe('updateIssue', () => {
        it('should update an issue when successful', async () => {
            const mockIssue = { id: 1, key: 'ABC-123' };
            jest.spyOn(integration.jiraClient.updateIssue, 'apply').mockResolvedValue(mockIssue);

            const updatedIssue = await integration.updateIssue(1, 'Updated Task', 'This is an updated task description.');
            expect(updatedIssue).toEqual(mockIssue);
        });

        it('should throw an error if update fails', async () => {
            jest.spyOn(integration.jiraClient.updateIssue, 'apply').mockRejectedValue(new Error('Update failed'));

            try {
                await integration.updateIssue(1, 'Updated Task', 'This is an updated task description.');
            } catch (error) {
                expect(error.message).toBe('Error updating issue: Update failed');
            }
        });
    });

    describe('deleteIssue', () => {
        it('should delete an issue when successful', async () => {
            jest.spyOn(integration.jiraClient.deleteIssue, 'apply').mockResolvedValue(undefined);

            await integration.deleteIssue(1);
            expect(jest.mocked(integration.jiraClient.deleteIssue).mock.calls.length).toBe(1);
        });

        it('should throw an error if deletion fails', async () => {
            jest.spyOn(integration.jiraClient.deleteIssue, 'apply').mockRejectedValue(new Error('Deletion failed'));

            try {
                await integration.deleteIssue(1);
            } catch (error) {
                expect(error.message).toBe('Error deleting issue: Deletion failed');
            }
        });
    });
});