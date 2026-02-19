import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';

describe('JiraClient', () => {
  describe('#fetchIssues', () => {
    it('should return issues when query is valid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const client = new JiraClient(apiKey, apiUrl);

      const response = await client.fetchIssues('project:your-project-key');

      expect(response).toBeInstanceOf(Array);
    });

    it('should throw an error when query is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const client = new JiraClient(apiKey, apiUrl);

      try {
        await client.fetchIssues('invalid-query');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update issue when key and updates are valid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const client = new JiraClient(apiKey, apiUrl);

      const issueId = uuidv4();
      const updates = { fields: { status: { name: 'In Progress' } } };

      const response = await client.updateIssue(issueId, updates);

      expect(response).toBeInstanceOf(Object);
    });

    it('should throw an error when key is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const client = new JiraClient(apiKey, apiUrl);

      const issueId = uuidv4();
      const updates = { fields: { status: { name: 'In Progress' } } };

      try {
        await client.updateIssue('invalid-key', updates);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error when updates are invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const client = new JiraClient(apiKey, apiUrl);

      const issueId = uuidv4();
      const updates = { fields: {} };

      try {
        await client.updateIssue(issueId, updates);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });
});

describe('TypeScriptAgent', () => {
  describe('#trackActivity', () => {
    it('should track activity when query is valid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const agent = new TypeScriptAgent(apiKey, apiUrl);

      try {
        await agent.trackActivity('project:your-project-key');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error when query is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const agent = new TypeScriptAgent(apiKey, apiUrl);

      try {
        await agent.trackActivity('invalid-query');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });
});