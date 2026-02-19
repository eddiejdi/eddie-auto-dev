const axios = require('axios');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssue(issueKey) {
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

  async addComment(issueKey, comment) {
    try {
      const response = await axios.post(`${this.url}/rest/api/2/issue/${issueKey}/comment`, { body: comment });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to add comment: ${error.message}`);
    }
  }

  async trackActivity(issueKey, activity) {
    try {
      const response = await axios.post(`${this.url}/rest/api/2/issue/${issueKey}/comment`, { body: `Tracking activity: ${activity}` });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to track activity: ${error.message}`);
    }
  }
}

const main = async () => {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');

  try {
    const issue = await jiraClient.getIssue('ABC-123');
    console.log(issue);

    const updates = { summary: 'Updated summary' };
    await jiraClient.updateIssue('ABC-123', updates);
    console.log('Issue updated successfully');

    const comment = 'This is a test comment';
    await jiraClient.addComment('ABC-123', comment);
    console.log('Comment added successfully');

    const activity = 'Activity logged';
    await jiraClient.trackActivity('ABC-123', activity);
    console.log('Activity tracked successfully');
  } catch (error) {
    console.error(error.message);
  }
};

if (require.main === module) {
  main();
}