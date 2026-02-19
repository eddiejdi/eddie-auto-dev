const axios = require('axios');
const fs = require('fs');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssue(issueKey) {
    const response = await axios.get(`${this.url}/rest/api/2/issue/${issueKey}`, {
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });

    return response.data;
  }

  async updateIssue(issueKey, data) {
    const response = await axios.put(`${this.url}/rest/api/2/issue/${issueKey}`, data, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }

  async createIssue(data) {
    const response = await axios.post(`${this.url}/rest/api/2/issue`, data, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }
}

class JavaScriptAgent {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async trackActivity(issueKey, activity) {
    const data = {
      issue: {
        key: issueKey
      },
      fields: {
        description: `JavaScript Agent tracking activity for ${issueKey}: ${activity}`
      }
    };

    await axios.post(`${this.url}/rest/api/2/issue/${issueKey}/comment`, data, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-token');
  const javascriptAgent = new JavaScriptAgent('https://your-javascript-agent-instance.com', 'your-token');

  try {
    // Get an issue
    await jiraClient.getIssue('ABC-123');
    console.log(`Issue: ABC-123`);

    // Update the issue
    await jiraClient.updateIssue('ABC-123', { status: 'In Progress' });
    console.log(`Updated Issue: ABC-123`);

    // Create a new issue
    const newIssue = await jiraClient.createIssue({
      projectKey: 'YOUR-PROJECT',
      summary: 'Test Issue with JavaScript Agent',
      description: 'This is a test issue created by the JavaScript Agent.'
    });
    console.log(`Created Issue: ${newIssue.key}`);

    // Track activity for an existing issue
    await javascriptAgent.trackActivity('ABC-123', 'User completed task');
  } catch (error) {
    console.error(error);
  }
}

if (require.main === module) {
  main();
}