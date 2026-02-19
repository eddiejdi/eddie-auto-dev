import axios from 'axios';
import { JiraClient } from './JiraClient';

describe('JiraClient', () => {
  describe('getIssue', () => {
    it('should return an issue with valid data', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const key = 'YOUR-ISSUE-KEY';

      try {
        const response = await jiraClient.getIssue(key);
        expect(response).toHaveProperty('key');
        expect(response).toHaveProperty('summary');
        expect(response).toHaveProperty('status');
      } catch (error) {
        console.error('Error fetching issue:', error);
      }
    });

    it('should throw an error if the issue key is invalid', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);

      try {
        await jiraClient.getIssue('INVALID-ISSUE-KEY');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid issue key');
      }
    });

    it('should throw an error if the token is invalid', async () => {
      const token = 'your-invalid-token';
      const jiraClient = new JiraClient(token);

      try {
        await jiraClient.getIssue('YOUR-ISSUE-KEY');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid token');
      }
    });
  });
});