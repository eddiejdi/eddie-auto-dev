import axios from 'axios';
import { expect } from 'chai';

describe('JiraClient', () => {
  describe('.fetchIssues()', () => {
    it('should fetch issues successfully with valid parameters', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      const response = await jiraClient.fetchIssues();
      expect(response).to.be.an('array');
    });

    it('should throw an error for invalid parameters', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      try {
        await jiraClient.fetchIssues({ jql: 'project = MyProject AND status = In Progress' });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid parameters');
      }
    });

    it('should handle errors during API request', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      try {
        await jiraClient.fetchIssues({ jql: 'project = MyProject AND status = In Progress' });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Error fetching issues');
      }
    });
  });

  describe('.updateIssue()', () => {
    it('should update an issue successfully with valid parameters', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      const response = await jiraClient.updateIssue('ABC123', 'Updated task summary');
      expect(response).to.be.an('object');
    });

    it('should throw an error for invalid parameters', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      try {
        await jiraClient.updateIssue('ABC123', '');
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid parameters');
      }
    });

    it('should handle errors during API request', async () => {
      const apiKey = 'your-jira-api-key';
      const apiUrl = 'https://your-jira-instance.atlassian.net';
      const jiraClient = new JiraClient(apiKey, apiUrl);

      try {
        await jiraClient.updateIssue('ABC123', '');
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Error updating issue');
      }
    });
  });
});