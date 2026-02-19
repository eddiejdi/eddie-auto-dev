const axios = require('axios');
const { JiraClient } = require('@jira/client');

describe('Jira Client Integration', () => {
  describe('Login', () => {
    it('should login successfully with valid credentials', async () => {
      const jiraClient = new JiraClient({
        auth: {
          username: 'your_username',
          password: 'your_password'
        },
        protocol: 'https',
        host: 'your_jira_host'
      });

      await jiraClient.login();
    });

    it('should throw an error if login fails with invalid credentials', async () => {
      const jiraClient = new JiraClient({
        auth: {
          username: 'invalid_username',
          password: 'invalid_password'
        },
        protocol: 'https',
        host: 'your_jira_host'
      });

      try {
        await jiraClient.login();
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid credentials');
      }
    });
  });

  describe('Create Issue', () => {
    it('should create an issue with valid fields', async () => {
      const jiraClient = new JiraClient({
        auth: {
          username: 'your_username',
          password: 'your_password'
        },
        protocol: 'https',
        host: 'your_jira_host'
      });

      await jiraClient.login();

      const issue = {
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: 'Test Issue',
          description: 'This is a test issue created using the JavaScript Agent with Jira.',
          priority: { name: 'High' }
        }
      };

      const result = await jiraClient.createIssue(issue);

      expect(result).toHaveProperty('id');
    });

    it('should throw an error if create issue fails with invalid fields', async () => {
      const jiraClient = new JiraClient({
        auth: {
          username: 'your_username',
          password: 'your_password'
        },
        protocol: 'https',
        host: 'your_jira_host'
      });

      await jiraClient.login();

      const issue = {
        fields: {
          project: { key: 'invalid_project_key' }, // Invalid project key
          summary: 'Test Issue',
          description: 'This is a test issue created using the JavaScript Agent with Jira.',
          priority: { name: 'High' }
        }
      };

      try {
        await jiraClient.createIssue(issue);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid project key');
      }
    });
  });
});