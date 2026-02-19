const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(apiKey, serverUrl) {
    this.apiKey = apiKey;
    this.serverUrl = serverUrl;
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
      const response = await axios.post(`${this.serverUrl}/rest/api/2/issue`, issueData, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error(error);
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
      const response = await axios.put(`${this.serverUrl}/rest/api/2/issue/${issueId}`, issueData, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error(error);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.serverUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error(error);
    }
  }

  async closeIssue(issueId) {
    const issueData = {
      fields: {
        status: { name: 'Closed' }
      }
    };

    try {
      const response = await axios.put(`${this.serverUrl}/rest/api/2/issue/${issueId}`, issueData, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error(error);
    }
  }

  async deleteIssue(issueId) {
    try {
      const response = await axios.delete(`${this.serverUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error(error);
    }
  }
}

async function main() {
  const apiKey = 'YOUR_JIRA_API_KEY';
  const serverUrl = 'https://your-jira-server.atlassian.net';

  const jiraClient = new JiraClient(apiKey, serverUrl);

  try {
    // Create an issue
    await jiraClient.createIssue('Test Issue', 'This is a test issue created using JavaScript Agent with Jira.');

    // Update the issue
    await jiraClient.updateIssue('1234567890', 'Updated Test Issue', 'This issue has been updated using JavaScript Agent with Jira.');

    // Get the issue
    const issue = await jiraClient.getIssue('1234567890');
    console.log(issue);

    // Close the issue
    await jiraClient.closeIssue('1234567890');

    // Delete the issue
    await jiraClient.deleteIssue('1234567890');
  } catch (error) {
    console.error(error);
  }
}

if (require.main === module) {
  main();
}