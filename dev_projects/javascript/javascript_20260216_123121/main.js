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

    return response.data.session.token;
  }

  async createIssue(title, description) {
    const token = await this.login();

    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    };

    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, issueData, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  async updateIssue(issueId, title, description) {
    const token = await this.login();

    const issueData = {
      fields: {
        summary: title,
        description: description
      }
    };

    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, issueData, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  async closeIssue(issueId) {
    const token = await this.login();

    const issueData = {
      fields: {
        status: { id: '10000' } // ID do status "Closed"
      }
    };

    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, issueData, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  async getIssue(issueId) {
    const token = await this.login();

    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }
}

class ScrumBoard {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async addTask(title, description) {
    const issueId = await this.createIssue(title, description);
    console.log(`Task added: ${issueId}`);
  }

  async updateTask(issueId, title, description) {
    await this.updateIssue(issueId, title, description);
    console.log(`Task updated: ${issueId}`);
  }

  async closeTask(issueId) {
    await this.closeIssue(issueId);
    console.log(`Task closed: ${issueId}`);
  }

  async getTasks() {
    const issues = await this.jiraClient.getIssues();
    return issues;
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const scrumBoard = new ScrumBoard(jiraClient);

  await scrumBoard.addTask('Implement JavaScript Agent', 'Tracking of activities in JavaScript');
  await scrumBoard.updateTask('Implement JavaScript Agent', 'Tracking of activities in JavaScript', 'Updated description');
  await scrumBoard.closeTask('YOUR_TASK_ID');

  const tasks = await scrumBoard.getTasks();
  console.log('Current tasks:', tasks);
}

if (require.main === module) {
  main().catch(console.error);
}