const axios = require('axios');

class JiraClient {
  constructor({ url, token }) {
    this.url = url;
    this.token = token;
  }

  async fetchIssue(issueKey) {
    try {
      const response = await axios.get(`${this.url}/rest/api/2/issue/${issueKey}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to fetch issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey, updates) {
    try {
      const response = await axios.put(`${this.url}/rest/api/2/issue/${issueKey}`, updates);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async trackActivity(issueKey, activity) {
    try {
      const response = await axios.post(`${this.url}/rest/api/2/activity`, { issueKey, activity });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to track activity: ${error.message}`);
    }
  }
}

async function main() {
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net',
    token: 'your-jira-token'
  });

  try {
    const issue = await jiraClient.fetchIssue('ABC-123');
    console.log(`Fetched issue: ${issue.key}`);

    const updates = { summary: 'Updated by JavaScript Agent' };
    await jiraClient.updateIssue(issue.key, updates);
    console.log(`Updated issue summary to: ${updates.summary}`);

    const activity = {
      type: 'comment',
      body: 'This is a comment from JavaScript Agent'
    };
    await jiraClient.trackActivity(issue.key, activity);
    console.log(`Tracked activity for issue ${issue.key}`);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}