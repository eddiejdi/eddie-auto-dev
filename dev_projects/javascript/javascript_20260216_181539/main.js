const axios = require('axios');

class JiraClient {
  constructor(apiKey, serverUrl) {
    this.apiKey = apiKey;
    this.serverUrl = serverUrl;
  }

  async createIssue(title, description, projectKey, issueType) {
    try {
      const response = await axios.post(`${this.serverUrl}/rest/api/2/issue`, {
        fields: {
          project: { key: projectKey },
          summary: title,
          description: description,
          issuetype: { name: issueType }
        }
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey, title, description) {
    try {
      const response = await axios.put(`${this.serverUrl}/rest/api/2/issue/${issueKey}`, {
        fields: {
          summary: title,
          description: description
        }
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.serverUrl}/rest/api/2/issue/${issueKey}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error getting issue:', error);
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(`${this.serverUrl}/rest/api/2/issue/${issueKey}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error deleting issue:', error);
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

module.exports = JiraClient;