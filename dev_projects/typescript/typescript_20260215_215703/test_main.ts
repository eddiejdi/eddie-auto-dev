import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('TypeScriptAgent', () => {
  describe('createIssue', () => {
    it('should create an issue with valid fields', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.createIssue('New Feature Request', 'Implement a new feature in the application')).to.not.throw();
    });

    it('should throw an error if fields are invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.createIssue('New Feature Request', '')).to.throw();
    });
  });

  describe('updateIssue', () => {
    it('should update an issue with valid fields', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.updateIssue('NEW_FEATURE_REQUEST_123', 'Add user authentication to the application', 'Fix login page issues')).to.not.throw();
    });

    it('should throw an error if fields are invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.updateIssue('NEW_FEATURE_REQUEST_123', '', '')).to.throw();
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue with valid id', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.deleteIssue('NEW_FEATURE_REQUEST_123')).to.not.throw();
    });

    it('should throw an error if id is invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const username = 'your-username';
      const password = 'your-password';

      const agent = new TypeScriptAgent(jiraUrl, username, password);

      await expect(agent.deleteIssue('')).to.throw();
    });
  });
});