const axios = require('axios');
const { JiraClient } = require('@jira/client');

describe('Jira Client', () => {
  describe('logEvent', () => {
    it('should create a comment for an issue with valid data', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      await logEvent('ABC-123', 'Task Completed', 'The task was completed successfully.');

      // Add assertions to verify the comment content
    });

    it('should throw an error if the issue does not exist', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      try {
        await logEvent('ABC-999', 'Task Completed', 'The task was completed successfully.');
      } catch (error) {
        // Add assertions to verify the error message
      }
    });
  });

  describe('monitorActivity', () => {
    it('should retrieve and log issues with valid data', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      await monitorActivity('ABC-123');

      // Add assertions to verify the issue summary and status
    });

    it('should throw an error if the issue does not exist', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      try {
        await monitorActivity('ABC-999');
      } catch (error) {
        // Add assertions to verify the error message
      }
    });
  });
});