const axios = require('axios');

class JiraClient {
  constructor(config) {
    this.config = config;
  }

  async createIssue(issueData) {
    try {
      const response = await axios.post(`${this.config.url}/rest/api/2/issue`, issueData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.config.username}:${this.config.password}`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueId, issueData) {
    try {
      const response = await axios.put(`${this.config.url}/rest/api/2/issue/${issueId}`, issueData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.config.username}:${this.config.password}`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.config.url}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.config.username}:${this.config.password}`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async closeIssue(issueId) {
    try {
      const response = await axios.put(`${this.config.url}/rest/api/2/issue/${issueId}`, { status: 'closed' }, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.config.username}:${this.config.password}`).toString('base64')}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to close issue: ${error.message}`);
    }
  }
}

module.exports = JiraClient;