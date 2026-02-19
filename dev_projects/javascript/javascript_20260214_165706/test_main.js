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

  async createIssue(projectKey, issueType, fields) {
    const token = await this.login();
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
      fields: { ...fields },
      project: { key: projectKey },
      issuetype: { name: issueType }
    }, {
      headers: {
        'Authorization': `Basic ${token}`
      }
    });
    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login();
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: { ...fields }
    }, {
      headers: {
        'Authorization': `Basic ${token}`
      }
    });
    return response.data;
  }

  async getIssue(issueId) {
    const token = await this.login();
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        'Authorization': `Basic ${token}`
      }
    });
    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async trackActivity(activity) {
    const issueId = uuidv4();
    try {
      await this.jiraClient.createIssue('YOUR_PROJECT_KEY', 'Bug', {
        summary: activity,
        description: `This is a test activity tracked by JavaScript Agent`
      });
      console.log(`Activity "${activity}" tracked successfully`);
    } catch (error) {
      console.error(`Error tracking activity "${activity}":`, error);
    }
  }

  async updateActivity(issueId, newActivity) {
    try {
      await this.jiraClient.updateIssue(issueId, {
        summary: newActivity
      });
      console.log(`Activity "${newActivity}" updated successfully`);
    } catch (error) {
      console.error(`Error updating activity "${newActivity}":`, error);
    }
  }

  async getIssueDetails(issueId) {
    try {
      const issue = await this.jiraClient.getIssue(issueId);
      console.log(`Issue details for ${issueId}:`, issue);
    } catch (error) {
      console.error(`Error fetching issue details for ${issueId}:`, error);
    }
  }
}

// Função main para execução do programa
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'YOUR_USERNAME';
  const password = 'YOUR_PASSWORD';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient);

  await javascriptAgent.trackActivity('New feature implemented');
  await javascriptAgent.updateActivity('New feature implemented', 'Feature implemented successfully');
  await javascriptAgent.getIssueDetails('YOUR_ISSUE_ID');
}

// Executa a função main
if (require.main === module) {
  main();
}