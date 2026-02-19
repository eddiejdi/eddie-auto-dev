const axios = require('axios');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssues(query) {
    try {
      const response = await axios.get(`${this.url}/rest/api/2/search`, {
        params: {
          jql: query,
          fields: ['summary', 'status', 'priority']
        },
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:x`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to fetch issues: ${error.message}`);
    }
  }

  async updateIssue(issueId, data) {
    try {
      const response = await axios.put(`${this.url}/rest/api/2/issue/${issueId}`, data, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:x`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async createIssue(data) {
    try {
      const response = await axios.post(`${this.url}/rest/api/2/issue`, data, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:x`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async deleteIssue(issueId) {
    try {
      const response = await axios.delete(`${this.url}/rest/api/2/issue/${issueId}`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:x`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

module.exports = JiraClient;