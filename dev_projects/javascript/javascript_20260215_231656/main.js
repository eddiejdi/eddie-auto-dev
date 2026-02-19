// Importações necessárias
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

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

    return response.data.token;
  }

  async createIssue(projectKey, issueType, summary, description) {
    const token = await this.login();
    const headers = { Authorization: `Bearer ${token}` };

    const issueData = {
      fields: {
        project: { key: projectKey },
        issuetype: { name: issueType },
        summary,
        description
      }
    };

    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, issueData, { headers });

    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login();
    const headers = { Authorization: `Bearer ${token}` };

    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, fields, { headers });

    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async trackActivity(issueId, activityType, description) {
    const issueData = {
      fields: {
        comment: {
          body: `${activityType}: ${description}`
        }
      }
    };

    await this.jiraClient.updateIssue(issueId, issueData);
  }
}

// Exemplo de uso
(async () => {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient);

  try {
    const issueId = 'YOUR-ISSUE-ID';
    await javascriptAgent.trackActivity(issueId, 'Task', 'This is a test task.');
    console.log('Activity tracked successfully!');
  } catch (error) {
    console.error('Error tracking activity:', error);
  }
})();