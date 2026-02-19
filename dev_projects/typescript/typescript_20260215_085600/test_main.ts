import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('JiraAgent', () => {
  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const agent = new JiraAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
      );

      await agent.createIssue('New Feature Request', 'Implement a new feature');
    });

    it('should throw an error if the title is empty', async () => {
      const agent = new JiraAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
      );

      await expect(agent.createIssue('', 'Implement a new feature')).rejects.toThrowError('Title cannot be empty');
    });

    it('should throw an error if the description is empty', async () => {
      const agent = new JiraAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
      );

      await expect(agent.createIssue('New Feature Request', '')).rejects.toThrowError('Description cannot be empty');
    });
  });

  describe('getIssues', () => {
    it('should return an array of issues', async () => {
      const agent = new JiraAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
      );

      await agent.createIssue('New Feature Request', 'Implement a new feature');
      await agent.createIssue('Bug Fix', 'Fix a bug in the application');

      const issues = await agent.getIssues();
      expect(issues.length).toBeGreaterThan(0);
    });

    it('should return an empty array if no issues are found', async () => {
      const agent = new JiraAgent(
        'https://your-jira-instance.atlassian.net',
        'your-username',
        'your-password'
      );

      await expect(agent.getIssues()).resolves.toEqual([]);
    });
  });
});