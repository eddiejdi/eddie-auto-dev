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
      fields: fields,
      project: { key: projectKey },
      issuetype: { name: issueType }
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login();
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: fields
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }

  async getIssue(issueId) {
    const token = await this.login();
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }
}

class JiraScrumBoard {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async createSprint(projectKey, sprintName, startDate, endDate) {
    const fields = {
      name: sprintName,
      startDate: startDate,
      endDate: endDate
    };
    return await this.jiraClient.createIssue(projectKey, 'Sprint', fields);
  }

  async addTaskToSprint(issueId, sprintId) {
    const fields = {
      status: 'In Progress'
    };
    return await this.jiraClient.updateIssue(issueId, fields);
  }
}

class JiraScrumBoardMonitor {
  constructor(jiraScrumBoard) {
    this.jiraScrumBoard = jiraScrumBoard;
  }

  async monitorSprint(projectKey, sprintId) {
    const sprint = await this.jiraScrumBoard.getIssue(sprintId);
    console.log(`Sprint ${sprint.name} started on ${sprint.startDate}`);
    // Add more logic to check for issues and alerts
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const sprintBoard = new JiraScrumBoard(jiraClient);
  const monitor = new JiraScrumBoardMonitor(sprintBoard);

  const projectKey = 'YOUR-PROJECT-KEY';
  const sprintName = 'Sprint 1';
  const startDate = '2023-04-01T00:00:00Z';
  const endDate = '2023-04-15T23:59:59Z';

  try {
    const sprint = await sprintBoard.createSprint(projectKey, sprintName, startDate, endDate);
    console.log(`Sprint ${sprint.name} created with ID ${sprint.id}`);
  } catch (error) {
    console.error('Error creating sprint:', error);
  }

  try {
    const issueId = 'YOUR-ISSUE-ID';
    await sprintBoard.addTaskToSprint(issueId, sprint.id);
  } catch (error) {
    console.error('Error adding task to sprint:', error);
  }

  try {
    await monitor.monitorSprint(projectKey, sprint.id);
  } catch (error) {
    console.error('Error monitoring sprint:', error);
  }
}

if (require.main === module) {
  main();
}