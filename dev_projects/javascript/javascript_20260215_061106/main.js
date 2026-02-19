const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor({ username, password }) {
    this.username = username;
    this.password = password;
    this.baseURL = 'https://your-jira-instance.atlassian.net/rest/api/3';
  }

  async login() {
    const response = await axios.post(`${this.baseURL}/session`, {
      username: this.username,
      password: this.password
    });
    return response.data.session.token;
  }

  async createIssue(projectKey, issueType, fields) {
    const token = await this.login();
    const response = await axios.post(`${this.baseURL}/issue`, {
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

  async logEvent(issueId, eventType, eventData) {
    const token = await this.login();
    const response = await axios.post(`${this.baseURL}/issue/${issueId}/comment`, {
      body: { value: eventData }
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }

  async sendNotification(issueId, message) {
    const token = await this.login();
    const response = await axios.post(`${this.baseURL}/issue/${issueId}/comment`, {
      body: { value: message }
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }
}

async function main() {
  const jiraClient = new JiraClient({
    username: 'your-jira-username',
    password: 'your-jira-password'
  });

  try {
    const issueId = 'ABC123';
    const eventType = 'Task Completed';
    const eventData = 'The task was completed successfully.';
    const notificationMessage = `Task ${eventType} for issue ${issueId}: ${eventData}`;

    await jiraClient.createIssue('YOUR-PROJECT-KEY', 'Task', {
      summary: `Task ${eventType} for issue ${issueId}`,
      description: eventData
    });

    await jiraClient.logEvent(issueId, eventType, eventData);

    await jiraClient.sendNotification(issueId, notificationMessage);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}