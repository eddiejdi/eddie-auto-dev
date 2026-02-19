const axios = require('axios');
const { expect } = require('chai');

class JiraClient {
  constructor(apiKey, serverUrl) {
    this.apiKey = apiKey;
    this.serverUrl = serverUrl;
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.serverUrl}/rest/api/2/issue/${issueId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to fetch issue ${issueId}: ${error.message}`);
    }
  }

  async updateIssue(issueId, updates) {
    try {
      const response = await axios.put(`${this.serverUrl}/rest/api/2/issue/${issueId}`, updates);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue ${issueId}: ${error.message}`);
    }
  }

  async trackActivity(issueId, activity) {
    try {
      const response = await axios.post(`${this.serverUrl}/rest/api/2/issue/${issueId}/comment`, { body: activity });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to track activity for issue ${issueId}: ${error.message}`);
    }
  }
}

describe('JiraClient', () => {
  describe('#getIssue', () => {
    it('should fetch an issue by ID with valid data', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'ISSUE-123';
      const expectedResponse = { key: 'ISSUE-123', summary: 'Sample Issue' };

      await expect(jiraClient.getIssue(issueId)).to.deep.equal(expectedResponse);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'INVALID-ID';
      await expect(jiraClient.getIssue(issueId)).to.throw('Failed to fetch issue INVALID-ID: Error fetching issue');
    });
  });

  describe('#updateIssue', () => {
    it('should update an issue with valid data', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'ISSUE-123';
      const updates = { summary: 'Updated Summary', description: 'Updated Description' };
      const expectedResponse = { key: 'ISSUE-123', summary: 'Updated Summary', description: 'Updated Description' };

      await expect(jiraClient.updateIssue(issueId, updates)).to.deep.equal(expectedResponse);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'INVALID-ID';
      await expect(jiraClient.updateIssue(issueId, {})).to.throw('Failed to update issue INVALID-ID: Error updating issue');
    });
  });

  describe('#trackActivity', () => {
    it('should track an activity for an issue with valid data', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'ISSUE-123';
      const activity = 'This is a new comment';
      const expectedResponse = { id: 123, body: 'This is a new comment' };

      await expect(jiraClient.trackActivity(issueId, activity)).to.deep.equal(expectedResponse);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      const apiKey = 'your_api_key';
      const serverUrl = 'https://your_jira_server_url';
      const jiraClient = new JiraClient(apiKey, serverUrl);

      const issueId = 'INVALID-ID';
      await expect(jiraClient.trackActivity(issueId, '')).to.throw('Failed to track activity for issue INVALID-ID: Error tracking activity');
    });
  });
});