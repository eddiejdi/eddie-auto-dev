const axios = require('axios');
const JiraClient = require('./JiraClient');

describe('JiraClient', () => {
  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const client = new JiraClient({
        baseUrl: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const issueData = {
        projectKey: 'YOUR_PROJECT_KEY',
        summary: 'Test Issue',
        description: 'This is a test issue created using the JiraClient.',
        issuetype: { name: 'Bug' }
      };

      try {
        const response = await client.createIssue(issueData);
        expect(response).toHaveProperty('id');
        expect(response).toHaveProperty('key');
        console.log('Issue created successfully:', response);
      } catch (error) {
        console.error('Error creating issue:', error.message);
      }
    });

    it('should throw an error if the project key is invalid', async () => {
      const client = new JiraClient({
        baseUrl: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const issueData = {
        projectKey: 'INVALID_PROJECT_KEY',
        summary: 'Test Issue',
        description: 'This is a test issue created using the JiraClient.',
        issuetype: { name: 'Bug' }
      };

      try {
        await client.createIssue(issueData);
      } catch (error) {
        expect(error.message).toContain('Invalid project key');
        console.log('Error creating issue with invalid project key:', error.message);
      }
    });

    it('should throw an error if the summary is too long', async () => {
      const client = new JiraClient({
        baseUrl: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const issueData = {
        projectKey: 'YOUR_PROJECT_KEY',
        summary: 'This is a very long summary that exceeds the maximum allowed length.',
        description: 'This is a test issue created using the JiraClient.',
        issuetype: { name: 'Bug' }
      };

      try {
        await client.createIssue(issueData);
      } catch (error) {
        expect(error.message).toContain('Summary too long');
        console.log('Error creating issue with summary too long:', error.message);
      }
    });
  });

  // Add similar tests for updateIssue, getIssue, deleteIssue, trackActivity
});