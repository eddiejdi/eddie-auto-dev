const axios = require('axios');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async getIssues() {
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/search`, {
      auth: { username: this.username, password: this.password },
      params: {
        jql: 'project = YourProjectKey AND status = Open',
        fields: ['summary', 'status'],
      },
    });

    return response.data.issues;
  }

  async updateIssue(issueId, summary) {
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: { summary },
    });

    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async trackActivity(issueId, activity) {
    const issues = await this.jiraClient.getIssues();
    const issue = issues.find(i => i.key === issueId);

    if (!issue) {
      throw new Error(`Issue ${issueId} not found`);
    }

    const updatedIssue = await this.jiraClient.updateIssue(issue.id, activity);
    console.log('Activity tracked:', updatedIssue.fields.summary);
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient);

  try {
    await javascriptAgent.trackActivity('ISSUE-123', 'Updated by JavaScript Agent');
  } catch (error) {
    console.error(error.message);
  }
}

if (require.main === module) {
  main();
}