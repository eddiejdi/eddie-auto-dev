import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('TypeScriptAgent', () => {
    let agent: TypeScriptAgent;

    beforeEach(() => {
        const jiraUrl = 'https://your-jira-instance.atlassian.net';
        const username = 'your-username';
        const password = 'your-password';
        agent = new TypeScriptAgent(jiraUrl, username, password);
    });

    describe('createIssue', () => {
        it('should create an issue with valid fields', async () => {
            await agent.createIssue('Task 1', 'This is a test task');
            expect(console.log).to.have.been.calledWith('Issue created successfully');
        });

        it('should throw an error if the project key is invalid', async () => {
            try {
                await agent.createIssue('Invalid Project Key', 'This is a test task');
            } catch (error) {
                expect(error.message).to.equal('Error creating issue: Invalid project key');
            }
        });

        it('should throw an error if the summary is empty', async () => {
            try {
                await agent.createIssue('', 'This is a test task');
            } catch (error) {
                expect(error.message).to.equal('Error creating issue: Summary cannot be empty');
            }
        });
    });

    describe('updateIssue', () => {
        it('should update an existing issue with valid fields', async () => {
            await agent.createIssue('Task 1', 'This is a test task');
            await agent.updateIssue('TASK-1', 'Updated task title', 'Updated task description');
            expect(console.log).to.have.been.calledWith('Issue updated successfully');
        });

        it('should throw an error if the issue key is invalid', async () => {
            try {
                await agent.updateIssue('Invalid Issue Key', 'This is a test task', 'Updated task description');
            } catch (error) {
                expect(error.message).to.equal('Error updating issue: Invalid issue key');
            }
        });

        it('should throw an error if the summary is empty', async () => {
            try {
                await agent.updateIssue('TASK-1', '', 'Updated task description');
            } catch (error) {
                expect(error.message).to.equal('Error updating issue: Summary cannot be empty');
            }
        });
    });

    describe('deleteIssue', () => {
        it('should delete an existing issue', async () => {
            await agent.createIssue('Task 1', 'This is a test task');
            await agent.deleteIssue('TASK-1');
            expect(console.log).to.have.been.calledWith('Issue deleted successfully');
        });

        it('should throw an error if the issue key is invalid', async () => {
            try {
                await agent.deleteIssue('Invalid Issue Key');
            } catch (error) {
                expect(error.message).to.equal('Error deleting issue: Invalid issue key');
            }
        });
    });
});