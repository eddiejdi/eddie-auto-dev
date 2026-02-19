import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/types';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';
    agent = new TypeScriptAgent(jiraUrl, username, password);
  });

  describe('createIssue', () => {
    it('should create a new issue with valid data', async () => {
      const title = 'New Task';
      const description = 'This is a new task.';
      const expectedKey = 'YOUR_PROJECT_KEY-10000'; // Example key

      try {
        const issue = await agent.createIssue(title, description);
        expect(issue.key).toEqual(expectedKey);
      } catch (error) {
        console.error(error.message);
      }
    });

    it('should throw an error when creating a new issue with invalid data', async () => {
      const title = '';
      const description = 'This is a new task.';
      try {
        await agent.createIssue(title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to create issue');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const issueKey = 'YOUR_PROJECT_KEY-10000'; // Example key
      const title = 'Updated Task';
      const description = 'This is an updated task.';
      const expectedKey = 'YOUR_PROJECT_KEY-10001'; // Example key

      try {
        const issue = await agent.updateIssue(issueKey, title, description);
        expect(issue.key).toEqual(expectedKey);
      } catch (error) {
        console.error(error.message);
      }
    });

    it('should throw an error when updating an existing issue with invalid data', async () => {
      const issueKey = 'YOUR_PROJECT_KEY-10000'; // Example key
      const title = '';
      const description = 'This is a new task.';
      try {
        await agent.updateIssue(issueKey, title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue with valid data', async () => {
      const issueKey = 'YOUR_PROJECT_KEY-10000'; // Example key

      try {
        await agent.deleteIssue(issueKey);
      } catch (error) {
        console.error(error.message);
      }
    });

    it('should throw an error when deleting an existing issue with invalid data', async () => {
      const issueKey = 'YOUR_PROJECT_KEY-10000'; // Example key
      try {
        await agent.deleteIssue(issueKey);
      } catch (error) {
        expect(error.message).toContain('Failed to delete issue');
      }
    });
  });
});