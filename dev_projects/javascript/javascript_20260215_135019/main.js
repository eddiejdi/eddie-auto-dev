const axios = require('axios');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async login(username, password) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/session`, { username, password });
    return response.data;
  }

  async createIssue(projectKey, issueType, fields) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, {
      project: { key: projectKey },
      issuetype: { name: issueType },
      fields
    }, this.options.headers);
    return response.data;
  }
}

const options = {
  baseUrl: 'https://your-jira-instance.atlassian.net',
  headers: {
    'Authorization': `Basic ${Buffer.from(`${options.username}:${options.password}`).toString('base64')}`
  }
};

async function main() {
  const jiraClient = new JiraClient(options);

  try {
    const loginResponse = await jiraClient.login('your-username', 'your-password');
    console.log('Login successful:', loginResponse);

    const issueFields = {
      summary: 'Test Issue',
      description: 'This is a test issue created using JavaScript Agent with Jira.',
      priority: { name: 'High' },
      assignee: { id: 'assignee-id' }
    };

    const issueResponse = await jiraClient.createIssue('YOUR-PROJECT-KEY', 'Bug', issueFields);
    console.log('Issue created successfully:', issueResponse);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}