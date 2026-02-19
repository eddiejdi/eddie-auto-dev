const axios = require('axios');

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

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey, title, description) {
    const issueData = {
      fields: {
        summary: title,
        description: description
      }
    };

    try {
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueKey}`, issueData, {
        auth: {
          username: this.username,
          password: this.password
        },
        headers: {
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(`${this.jiraUrl}/rest/api/2/issue/${issueKey}`, {
        auth: {
          username: this.username,
          password: this.password
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

// Example usage:
(async () => {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

  try {
    const issue = await jiraClient.createIssue('New Task', 'This is a new task for the project.');
    console.log(issue);

    // Update the issue
    await jiraClient.updateIssue(issue.key, 'Updated Task', 'This task has been updated.');

    // Delete the issue
    await jiraClient.deleteIssue(issue.key);
  } catch (error) {
    console.error(error.message);
  }
})();