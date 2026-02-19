const axios = require('axios');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async createIssue(issueData) {
    try {
      const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, issueData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.options.username}:${this.options.password}`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueId, updateData) {
    try {
      const response = await axios.put(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, updateData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.options.username}:${this.options.password}`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.options.username}:${this.options.password}`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async deleteIssue(issueId) {
    try {
      const response = await axios.delete(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.options.username}:${this.options.password}`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }

  async trackActivity(issueId, activityData) {
    try {
      const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue/${issueId}/comment`, activityData, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${this.options.username}:${this.options.password}`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to track activity: ${error.message}`);
    }
  }
}

module.exports = JiraClient;