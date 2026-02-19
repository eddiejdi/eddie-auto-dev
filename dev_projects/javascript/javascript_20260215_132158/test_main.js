const { expect } = require('chai');
const axios = require('axios');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async getIssues() {
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/search`, {
      auth: { username: this.username, password: this.password },
      params: {
        jql: 'project = YourProjectKey AND status = Open',
        fields: ['summary', 'status'],
      },
    });

    return response.data.issues;
  }

  async updateIssue(issueId, summary) {
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: { summary },
    });

    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async trackActivity(issueId, activity) {
    const issues = await this.jiraClient.getIssues();
    const issue = issues.find(i => i.key === issueId);

    if (!issue) {
      throw new Error(`Issue ${issueId} not found`);
    }

    const updatedIssue = await this.jiraClient.updateIssue(issue.id, activity);
    console.log('Activity tracked:', updatedIssue.fields.summary);
  }
}

describe('JiraClient', () => {
  describe('getIssues', () => {
    it('should return issues when provided with valid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const response = await jiraClient.getIssues();
      expect(response).to.be.an.array;
    });

    it('should throw an error when provided with invalid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(jiraClient.getIssues()).rejects.to.be.an(Error);
    });
  });

  describe('updateIssue', () => {
    it('should update an issue when provided with valid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await jiraClient.updateIssue('ISSUE-123', 'Updated by JavaScript Agent');
    });

    it('should throw an error when provided with invalid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(jiraClient.updateIssue('ISSUE-123')).rejects.to.be.an(Error);
    });
  });
});

describe('JavaScriptAgent', () => {
  describe('trackActivity', () => {
    it('should track activity when provided with valid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await jiraClient.trackActivity('ISSUE-123', 'Updated by JavaScript Agent');
    });

    it('should throw an error when provided with invalid parameters', async () => {
      const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(jiraClient.trackActivity('ISSUE-123')).rejects.to.be.an(Error);
    });
  });
});