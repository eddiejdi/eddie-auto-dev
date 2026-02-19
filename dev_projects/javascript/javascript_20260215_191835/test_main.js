const axios = require('axios');
const assert = require('assert');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async getIssue(issueKey) {
    const response = await axios.get(`${this.options.baseUrl}/rest/api/2/issue/${issueKey}`);
    return response.data;
  }
}

async function main() {
  const jiraOptions = {
    baseUrl: 'https://your-jira-instance.atlassian.net',
    username: 'your-username',
    password: 'your-password'
  };

  const jiraClient = new JiraClient(jiraOptions);

  try {
    const issueKey = 'YOUR-ISSUE-KEY';
    const issue = await jiraClient.getIssue(issueKey);
    assert.strictEqual(issue.fields.summary, 'Your Issue Summary', `Issue summary should be 'Your Issue Summary'`);
  } catch (error) {
    console.error('Error fetching issue:', error.message);
  }
}

if (require.main === module) {
  main();
}