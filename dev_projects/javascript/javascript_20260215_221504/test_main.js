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
        issuetype: { name: 'Task' }
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

  async updateIssue(issueId, title, description) {
    const issueData = {
      fields: {
        summary: title,
        description: description
      }
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
          jql: 'project=YOUR_PROJECT_KEY'
        }
      });

      console.log('Issues retrieved:', response.data);
    } catch (error) {
      console.error('Error retrieving issues:', error);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
        auth: {
          username: this.username,
          password: this.password
        }
      });

      console.log('Issue retrieved:', response.data);
    } catch (error) {
      console.error('Error retrieving issue:', error);
    }
  }

  async deleteIssue(issueId) {
    try {
      const response = await axios.delete(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
        auth: {
          username: this.username,
          password: this.password
        }
      });

      console.log('Issue deleted:', response.data);
    } catch (error) {
      console.error('Error deleting issue:', error);
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
    await jiraClient.createIssue('Task 1', 'This is a test task.');
    await jiraClient.updateIssue('YOUR_ISSUE_ID', 'Updated Task 1', 'This is an updated test task.');
    await jiraClient.getIssues();
    await jiraClient.getIssue('YOUR_ISSUE_ID');
    await jiraClient.deleteIssue('YOUR_ISSUE_ID');
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}