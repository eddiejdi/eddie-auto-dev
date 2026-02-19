const axios = require('axios');

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

async function main() {
  const apiKey = 'your_api_key';
  const serverUrl = 'https://your_jira_server_url';

  const jiraClient = new JiraClient(apiKey, serverUrl);

  try {
    const issue = await jiraClient.getIssue('ISSUE-123');
    console.log(`Fetched issue: ${issue.key}`);

    const updates = {
      summary: 'Updated summary',
      description: 'Updated description'
    };

    await jiraClient.updateIssue('ISSUE-123', updates);
    console.log(`Updated issue: ${updates.summary}`);

    const activity = 'This is a new comment';
    await jiraClient.trackActivity('ISSUE-123', activity);
    console.log(`Tracked activity for issue: ${activity}`);
  } catch (error) {
    console.error(error.message);
  }
}

if (require.main === module) {
  main();
}