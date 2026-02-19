const axios = require('axios');
const { expect } = require('chai');

describe('JiraClient', () => {
  describe('.getIssue', () => {
    it('should return the issue data for a valid issue key', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');
      const issueKey = 'JIRA-123';
      const response = await jiraClient.getIssue(issueKey);
      expect(response).to.have.property('key').equal(issueKey);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');
      const issueKey = 'INVALID-123';
      await expect(jiraClient.getIssue(issueKey)).to.be.rejected;
    });
  });

  describe('.updateIssue', () => {
    it('should update the issue data for a valid issue key and new data', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');
      const issueKey = 'JIRA-123';
      const updatedData = {
        fields: {
          status: {
            name: 'In Progress',
          },
        },
      };
      const response = await jiraClient.updateIssue(issueKey, updatedData);
      expect(response).to.have.property('key').equal(issueKey);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');
      const issueKey = 'INVALID-123';
      const updatedData = {
        fields: {
          status: {
            name: 'In Progress',
          },
        },
      };
      await expect(jiraClient.updateIssue(issueKey, updatedData)).to.be.rejected;
    });

    it('should throw an error if the new data is invalid', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');
      const issueKey = 'JIRA-123';
      const updatedData = {
        fields: {
          status: {
            name: 'In Progress',
          },
        },
      };
      await expect(jiraClient.updateIssue(issueKey, updatedData)).to.be.rejected;
    });
  });
});