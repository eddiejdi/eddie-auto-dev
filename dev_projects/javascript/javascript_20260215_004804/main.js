const axios = require('axios');

class JiraClient {
  constructor(apiToken, baseUrl) {
    this.apiToken = apiKey;
    this.baseUrl = baseUrl;
  }

  async createIssue(title, description) {
    try {
      const response = await axios.post(`${this.baseUrl}/rest/api/2/issue`, {
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description
        }
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueId, title, description) {
    try {
      const response = await axios.put(`${this.baseUrl}/rest/api/2/issue/${issueId}`, {
        fields: {
          summary: title,
          description: description
        }
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.baseUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async deleteIssue(issueId) {
    try {
      const response = await axios.delete(`${this.baseUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

module.exports = JiraClient;