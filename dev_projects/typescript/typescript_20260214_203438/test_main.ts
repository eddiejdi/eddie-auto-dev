import { Client } from '@atlassian/issue-client';
import { Issue } from '@atlassian/issue-client';

describe('Client', () => {
  describe('searchIssues', () => {
    it('should return issues when provided with a valid JQL query', async () => {
      const client = new Client({
        serverUrl: 'https://your-jira-server.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const response = await client.searchIssues({ jql: 'project = YOUR_PROJECT_KEY' });
      expect(response.length).toBeGreaterThan(0);
    });

    it('should throw an error when provided with an invalid JQL query', async () => {
      const client = new Client({
        serverUrl: 'https://your-jira-server.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      try {
        await client.searchIssues({ jql: 'project = YOUR_PROJECT_KEY' });
      } catch (error) {
        expect(error.message).toContain('Invalid JQL query');
      }
    });

    it('should throw an error when provided with a null or undefined JQL query', async () => {
      const client = new Client({
        serverUrl: 'https://your-jira-server.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      try {
        await client.searchIssues({ jql: null });
      } catch (error) {
        expect(error.message).toContain('Invalid JQL query');
      }

      try {
        await client.searchIssues({ jql: undefined });
      } catch (error) {
        expect(error.message).toContain('Invalid JQL query');
      }
    });

    it('should throw an error when provided with a non-string JQL query', async () => {
      const client = new Client({
        serverUrl: 'https://your-jira-server.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      try {
        await client.searchIssues({ jql: 123 });
      } catch (error) {
        expect(error.message).toContain('Invalid JQL query');
      }
    });
  });
});