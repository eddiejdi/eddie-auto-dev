import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

describe('TypeScriptAgent', () => {
    let client: JiraClient;

    beforeEach(() => {
        client = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            auth: {
                username: 'your-username',
                password: 'your-password'
            }
        });
    });

    describe('createIssue', () => {
        it('should create an issue with valid data', async () => {
            const title = 'TypeScript Integration';
            const description = 'This is a test issue for TypeScript integration.';
            const issue = await client.createIssue(title, description);
            expect(issue).toBeDefined();
        });

        it('should throw an error if the project key is invalid', async () => {
            const title = 'Invalid Project Key';
            const description = 'This is a test issue for TypeScript integration.';
            try {
                await client.createIssue(title, description);
                fail('Expected an error to be thrown');
            } catch (error) {
                expect(error.message).toBe('Failed to create issue: Invalid project key');
            }
        });
    });

    describe('updateIssue', () => {
        it('should update an existing issue with valid data', async () => {
            const title = 'Updated Title';
            const description = 'Updated Description';
            const issue = await client.createIssue('TypeScript Integration', 'This is a test issue for TypeScript integration.');
            const updatedIssue = await client.updateIssue(issue.id, title, description);
            expect(updatedIssue).toBeDefined();
        });

        it('should throw an error if the issue ID is invalid', async () => {
            const title = 'Invalid Issue ID';
            const description = 'This is a test issue for TypeScript integration.';
            try {
                await client.updateIssue('invalid-id', title, description);
                fail('Expected an error to be thrown');
            } catch (error) {
                expect(error.message).toBe('Failed to update issue: Invalid issue ID');
            }
        });
    });

    describe('deleteIssue', () => {
        it('should delete an existing issue', async () => {
            const issue = await client.createIssue('TypeScript Integration', 'This is a test issue for TypeScript integration.');
            await client.deleteIssue(issue.id);
            try {
                await client.getIssue(issue.id);
                fail('Expected an error to be thrown');
            } catch (error) {
                expect(error.message).toBe('Failed to delete issue: Issue not found');
            }
        });

        it('should throw an error if the issue ID is invalid', async () => {
            try {
                await client.deleteIssue('invalid-id');
                fail('Expected an error to be thrown');
            } catch (error) {
                expect(error.message).toBe('Failed to delete issue: Invalid issue ID');
            }
        });
    });
});