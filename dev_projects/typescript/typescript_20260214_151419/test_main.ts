import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/model/issue';
import { AssertionError } from 'assert';

describe('TypeScriptAgent', () => {
    let agent: TypeScriptAgent;

    beforeEach(() => {
        agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
    });

    describe('createIssue', () => {
        it('should create an issue with valid data', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                const issue = await agent.createIssue(title, description);
                expect(issue).toBeDefined();
                expect(issue.fields.project.key).toBe('YOUR_PROJECT_KEY');
                expect(issue.fields.summary).toBe(title);
                expect(issue.fields.description).toBe(description);
                expect(issue.fields.issuetype.name).toBe('Bug');
            } catch (error) {
                throw new AssertionError(`Error creating issue: ${error}`);
            }
        });

        it('should throw an error if the project key is invalid', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                await agent.createIssue(title, description, { key: 'INVALID_PROJECT_KEY' });
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Invalid project key');
            }
        });

        it('should throw an error if the summary is empty', async () => {
            const title = '';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                await agent.createIssue(title, description);
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Summary cannot be empty');
            }
        });
    });

    describe('updateIssue', () => {
        it('should update an issue with valid data', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                const issue = await agent.createIssue(title, description);
                const updatedTitle = 'Updated TypeScript Agent Integration';
                const updatedDescription = 'This is an updated test issue.';
                const updatedIssue = await agent.updateIssue(issue.id, { summary: updatedTitle, description: updatedDescription });
                expect(updatedIssue).toBeDefined();
                expect(updatedIssue.fields.summary).toBe(updatedTitle);
                expect(updatedIssue.fields.description).toBe(updatedDescription);
            } catch (error) {
                throw new AssertionError(`Error updating issue: ${error}`);
            }
        });

        it('should throw an error if the issue ID is invalid', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                await agent.createIssue(title, description);
                const invalidId = 'INVALID_ID';
                await agent.updateIssue(invalidId, { summary: updatedTitle, description: updatedDescription });
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Invalid issue ID');
            }
        });

        it('should throw an error if the title is empty', async () => {
            const title = '';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                await agent.createIssue(title, description);
                const updatedTitle = 'Updated TypeScript Agent Integration';
                const updatedDescription = 'This is an updated test issue.';
                await agent.updateIssue('12345', { summary: updatedTitle, description: updatedDescription });
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Summary cannot be empty');
            }
        });

        it('should throw an error if the description is empty', async () => {
            const title = 'TypeScript Agent Integration';
            const description = '';
            try {
                await agent.createIssue(title, description);
                const updatedTitle = 'Updated TypeScript Agent Integration';
                const updatedDescription = 'This is an updated test issue.';
                await agent.updateIssue('12345', { summary: updatedTitle, description: updatedDescription });
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Description cannot be empty');
            }
        });
    });

    describe('deleteIssue', () => {
        it('should delete an issue with valid data', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                const issue = await agent.createIssue(title, description);
                await agent.deleteIssue(issue.id);
                expect(issue).toBeUndefined();
            } catch (error) {
                throw new AssertionError(`Error deleting issue: ${error}`);
            }
        });

        it('should throw an error if the issue ID is invalid', async () => {
            const title = 'TypeScript Agent Integration';
            const description = 'This is a test issue for the TypeScript Agent integration.';
            try {
                await agent.createIssue(title, description);
                const invalidId = 'INVALID_ID';
                await agent.deleteIssue(invalidId);
            } catch (error) {
                expect(error).toBeDefined();
                expect(error.message).toBe('Invalid issue ID');
            }
        });
    });
});