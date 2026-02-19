const axios = require('axios');

class JiraClient {
  constructor(apiToken) {
    this.apiToken = apiToken;
  }

  async createIssue(title, description) {
    try {
      const response = await axios.post(
        'https://your-jira-instance.atlassian.net/rest/api/2/issue',
        {
          fields: {
            project: { key: 'YOUR_PROJECT_KEY' },
            summary: title,
            description: description,
            issuetype: { name: 'Bug' },
          },
        },
        {
          headers: {
            Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(
        `https://your-jira-instance.atlassian.net/rest/api/2/issue/${issueKey}`,
        {
          headers: {
            Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error getting issue:', error);
      throw error;
    }
  }

  async updateIssue(issueKey, fields) {
    try {
      const response = await axios.put(
        `https://your-jira-instance.atlassian.net/rest/api/2/issue/${issueKey}`,
        { fields },
        {
          headers: {
            Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(
        `https://your-jira-instance.atlassian.net/rest/api/2/issue/${issueKey}`,
        {
          headers: {
            Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error deleting issue:', error);
      throw error;
    }
  }
}

module.exports = JiraClient;