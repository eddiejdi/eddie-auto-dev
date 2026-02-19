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

  async createIssue(title, description) {
    const token = await this.login();
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Task' }
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

  async getIssue(issueId) {
    const token = await this.login();
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
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
        status: { name: 'Closed' }
      }
    };

    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, issueData, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return response.data;
  }

  async deleteIssue(issueId) {
    const token = await this.login();
    const response = await axios.delete(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return response.data;
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');

  try {
    // Create a new issue
    const newIssue = await jiraClient.createIssue('Task 1', 'This is the first task.');
    console.log('New Issue:', newIssue);

    // Update an existing issue
    const updatedIssue = await jiraClient.updateIssue(newIssue.id, 'Updated Task 1', 'This is the updated task.');
    console.log('Updated Issue:', updatedIssue);

    // Get an issue
    const issue = await jiraClient.getIssue(newIssue.id);
    console.log('Issue:', issue);

    // Close an issue
    const closedIssue = await jiraClient.closeIssue(newIssue.id);
    console.log('Closed Issue:', closedIssue);

    // Delete an issue
    const deletedIssue = await jiraClient.deleteIssue(newIssue.id);
    console.log('Deleted Issue:', deletedIssue);
  } catch (error) {
    console.error(error);
  }
}

if (require.main === module) {
  main();
}