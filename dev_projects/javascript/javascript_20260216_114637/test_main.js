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
    const headers = { Authorization: `Bearer ${token}` };
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
      projectKey,
      issuetype: issueType,
      fields
    }, { headers });
    return response.data;
  }
}

class Logger {
  log(message) {
    console.log(`[${new Date().toISOString()}] ${message}`);
  }
}

class TaskManager {
  constructor(jiraClient, logger) {
    this.jiraClient = jiraClient;
    this.logger = logger;
  }

  async createTask(projectKey, issueType, fields) {
    try {
      const token = await this.jiraClient.login();
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
        projectKey,
        issuetype: issueType,
        fields
      }, { headers });
      return response.data;
    } catch (error) {
      this.logger.log(`Error creating task: ${error.message}`);
      throw error;
    }
  }

  async updateTask(taskId, fields) {
    try {
      const token = await this.jiraClient.login();
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${taskId}`, fields, { headers });
      return response.data;
    } catch (error) {
      this.logger.log(`Error updating task: ${error.message}`);
      throw error;
    }
  }

  async deleteTask(taskId) {
    try {
      const token = await this.jiraClient.login();
      const headers = { Authorization: `Bearer ${token}` };
      await axios.delete(`${this.jiraUrl}/rest/api/2/issue/${taskId}`, { headers });
    } catch (error) {
      this.logger.log(`Error deleting task: ${error.message}`);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const logger = new Logger();
  const jiraClient = new JiraClient(jiraUrl, username, password);
  const taskManager = new TaskManager(jiraClient, logger);

  try {
    // Criar uma nova tarefa
    const issueType = 'Task';
    const fields = {
      summary: 'Implement SCRUM-9 in JavaScript',
      description: 'This is a test for implementing SCRUM-9 in JavaScript',
      priority: 'High'
    };
    await taskManager.createTask('YOUR_PROJECT_KEY', issueType, fields);
    console.log(`New task created: ${fields.key}`);

    // Atualizar uma tarefa
    const taskId = fields.id;
    const updatedFields = {
      summary: 'Implement SCRUM-9 in JavaScript (Updated)',
      description: 'This is a test for implementing SCRUM-9 in JavaScript (Updated)'
    };
    await taskManager.updateTask(taskId, updatedFields);
    console.log(`Task updated: ${taskId}`);

    // Deletar uma tarefa
    await taskManager.deleteTask(taskId);
    console.log(`Task deleted: ${taskId}`);
  } catch (error) {
    logger.log(error.message);
  }
}

if (require.main === module) {
  main();
}