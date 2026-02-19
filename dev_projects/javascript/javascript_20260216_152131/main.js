const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async createIssue(title, description) {
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    };

    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, issueData, {
        auth: {
          username: this.username,
          password: this.password
        },
        headers: {
          'Content-Type': 'application/json'
        }
      });

      console.log('Issue created:', response.data);
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async updateIssue(issueId, description) {
    const issueData = {
      fields: { description }
    };

    try {
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, issueData, {
        auth: {
          username: this.username,
          password: this.password
        },
        headers: {
          'Content-Type': 'application/json'
        }
      });

      console.log('Issue updated:', response.data);
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async getIssues() {
    try {
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/search`, {
        auth: {
          username: this.username,
          password: this.password
        },
        params: {
          jql: 'project = YOUR_PROJECT_KEY'
        }
      });

      console.log('Issues:', response.data);
    } catch (error) {
      console.error('Error getting issues:', error);
    }
  }

  async logEvent(eventData) {
    try {
      const eventId = uuidv4();
      const eventUrl = `${this.jiraUrl}/rest/api/2/issue/${eventId}`;

      const response = await axios.post(eventUrl, eventData, {
        auth: {
          username: this.username,
          password: this.password
        },
        headers: {
          'Content-Type': 'application/json'
        }
      });

      console.log('Event logged:', response.data);
    } catch (error) {
      console.error('Error logging event:', error);
    }
  }
}

async function main() {
  const jiraClient = new JiraClient(
    'https://your-jira-instance.atlassian.net',
    'your-username',
    'your-password'
  );

  await jiraClient.createIssue('Test Issue', 'This is a test issue.');
  await jiraClient.updateIssue('10101', 'Updated description of the issue.');
  await jiraClient.getIssues();
  await jiraClient.logEvent({ type: 'info', message: 'Hello from Jira Client!' });
}

if (require.main === module) {
  main();
}