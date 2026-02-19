// Import necessary libraries and modules
const axios = require('axios');
const fs = require('fs');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.options.baseUrl}/rest/api/2/issue/${issueKey}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to retrieve issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey, updates) {
    try {
      const response = await axios.put(`${this.options.baseUrl}/rest/api/2/issue/${issueKey}`, updates);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async logActivity(issueKey, activity) {
    try {
      const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue/${issueKey}/comment`, { body: activity });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to log activity: ${error.message}`);
    }
  }

  async trackActivity(issueKey, activity) {
    try {
      const issue = await this.getIssue(issueKey);
      const updates = {
        fields: {
          comments: [
            { body: activity },
            ...issue.fields.comments
          ]
        }
      };
      await this.updateIssue(issueKey, updates);
      return `Activity logged for issue ${issueKey}`;
    } catch (error) {
      throw new Error(`Failed to track activity: ${error.message}`);
    }
  }
}

// Example usage of the JiraClient class
const options = {
  baseUrl: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
};

(async () => {
  const client = new JiraClient(options);

  try {
    await client.trackActivity('ABC-123', 'This is a test activity.');
    console.log('Activity logged successfully');
  } catch (error) {
    console.error(error.message);
  }
})();