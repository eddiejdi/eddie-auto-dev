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
      fields: {
        project: { key: projectKey },
        summary: fields.summary,
        description: fields.description,
        issuetype: { name: issueType }
      },
      token
    });

    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login();
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields,
      token
    });

    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient, issueType, projectKey) {
    this.jiraClient = jiraClient;
    this.issueType = issueType;
    this.projectKey = projectKey;
  }

  async monitorActivity() {
    const token = await this.jiraClient.login();
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/search`, {
      fields: ['id', 'summary'],
      jql: `project=${this.projectKey} AND issuetype=${this.issueType}`,
      expand: 'fields',
      token
    });

    return response.data;
  }

  async registerEvent(eventData) {
    const issueId = eventData.id;
    const fields = {
      description: eventData.description,
      status: 'In Progress'
    };
    await this.jiraClient.updateIssue(issueId, fields);
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';
  const projectKey = 'YOUR_PROJECT_KEY';
  const issueType = 'YOUR_ISSUE_TYPE';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient, issueType, projectKey);

  try {
    const activity = await javascriptAgent.monitorActivity();
    console.log('Activity:', activity);

    const eventData = {
      id: '12345',
      description: 'This is a test event'
    };

    await javascriptAgent.registerEvent(eventData);
    console.log('Event registered successfully');
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}