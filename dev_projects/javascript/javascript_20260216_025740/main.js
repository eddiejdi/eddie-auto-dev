const axios = require('axios');
const { log } = console;

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async login() {
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/session`, {
      username: this.username,
      password: this.password
    });
    return response.data;
  }

  async createIssue(issueData) {
    const { issueType, summary, description } = issueData;
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        issuetype: { name: issueType },
        summary,
        description
      }
    });
    return response.data;
  }

  async updateIssue(issueId, issueData) {
    const { status } = issueData;
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: {
        status: { id: status }
      }
    });
    return response.data;
  }

  async getIssue(issueId) {
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`);
    return response.data;
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');

  try {
    const loginResponse = await jiraClient.login();
    log(`Logged in as ${loginResponse.name}`);

    const issueData = {
      issueType: 'Bug',
      summary: 'Test bug',
      description: 'This is a test bug for the JavaScript agent.'
    };

    const issueId = await jiraClient.createIssue(issueData);
    log(`Created issue with ID ${issueId}`);

    // Simulate some activity
    await new Promise(resolve => setTimeout(resolve, 5000));

    const updateData = {
      status: 'In Progress'
    };

    await jiraClient.updateIssue(issueId, updateData);
    log(`Updated issue to status ${updateData.status}`);

    const issue = await jiraClient.getIssue(issueId);
    log(`Issue details: ${JSON.stringify(issue)}`);
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}