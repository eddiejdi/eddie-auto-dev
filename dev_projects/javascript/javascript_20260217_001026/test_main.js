const axios = require('axios');
const { expect } = require('chai');

describe('JiraClient', () => {
  describe('#fetchIssue', () => {
    it('should fetch an issue with valid data', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const issueKey = 'ABC-123';
      const response = await jiraClient.fetchIssue(issueKey);
      expect(response).to.have.property('key').equal(issueKey);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const invalidIssueKey = 'ABC';
      await expect(jiraClient.fetchIssue(invalidIssueKey)).to.be.rejected;
    });
  });

  describe('#updateIssue', () => {
    it('should update an issue with valid data', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const issueKey = 'ABC-123';
      const updates = { summary: 'Updated by JavaScript Agent' };
      const response = await jiraClient.updateIssue(issueKey, updates);
      expect(response).to.have.property('key').equal(issueKey);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const invalidIssueKey = 'ABC';
      await expect(jiraClient.updateIssue(invalidIssueKey, updates)).to.be.rejected;
    });
  });

  describe('#trackActivity', () => {
    it('should track an activity with valid data', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const issueKey = 'ABC-123';
      const activity = {
        type: 'comment',
        body: 'This is a comment from JavaScript Agent'
      };
      const response = await jiraClient.trackActivity(issueKey, activity);
      expect(response).to.have.property('key').equal(issueKey);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        token: 'your-jira-token'
      });

      const invalidIssueKey = 'ABC';
      await expect(jiraClient.trackActivity(invalidIssueKey, activity)).to.be.rejected;
    });
  });
});