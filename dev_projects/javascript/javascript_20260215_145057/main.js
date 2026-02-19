const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async login() {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/session`, {
        username: this.username,
        password: this.password
      });
      return response.data.token;
    } catch (error) {
      throw new Error('Failed to log in');
    }
  }

  async createIssue(projectKey, issueType, summary, description) {
    try {
      const token = await this.login();
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
        fields: {
          project: { key: projectKey },
          issuetype: { name: issueType },
          summary,
          description
        }
      }, {
        headers: {
          'Authorization': `Basic ${token}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error('Failed to create issue');
    }
  }

  async monitorEvents() {
    try {
      const token = await this.login();
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/watcher/list`, {
        headers: {
          'Authorization': `Basic ${token}`
        }
      });
      return response.data.watchers;
    } catch (error) {
      throw new Error('Failed to monitor events');
    }
  }

  async registerActivity(issueKey, activityType, description) {
    try {
      const token = await this.login();
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue/${issueKey}/comment`, {
        body: {
          comment: {
            author: { name: 'Your Name' },
            body: description
          }
        }
      }, {
        headers: {
          'Authorization': `Basic ${token}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error('Failed to register activity');
    }
  }
}

async function main() {
  const jiraClient = new JiraClient(
    'https://your-jira-instance.atlassian.net',
    'your-username',
    'your-password'
  );

  try {
    const issueKey = uuidv4();
    const projectKey = 'YOUR_PROJECT_KEY';
    const issueType = 'YOUR_ISSUE_TYPE';

    // Create an issue
    const createdIssue = await jiraClient.createIssue(projectKey, issueType, 'Test Issue', 'This is a test issue.');
    console.log('Created issue:', createdIssue);

    // Monitor events
    const events = await jiraClient.monitorEvents();
    console.log('Monitored events:', events);

    // Register activity on the issue
    const registeredActivity = await jiraClient.registerActivity(issueKey, 'COMMENT', 'This is a test comment.');
    console.log('Registered activity:', registeredActivity);
  } catch (error) {
    console.error(error.message);
  }
}

if (require.main === module) {
  main();
}