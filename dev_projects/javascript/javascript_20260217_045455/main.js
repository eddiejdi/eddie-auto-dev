const axios = require('axios');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async createIssue(title, description) {
    const payload = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Task' }
      }
    };

    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, payload, {
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
    const payload = {
      fields: {
        summary: title,
        description: description
      }
    };

    try {
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueKey}`, payload, {
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

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueKey}`, {
        auth: {
          username: this.username,
          password: this.password
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');

  try {
    const issue = await jiraClient.createIssue('New Task', 'This is a new task description');
    console.log(`Created issue: ${issue.key}`);

    const updatedIssue = await jiraClient.updateIssue(issue.key, 'Updated Task', 'This is an updated task description');
    console.log(`Updated issue: ${updatedIssue.key}`);

    const retrievedIssue = await jiraClient.getIssue(issue.key);
    console.log(`Retrieved issue: ${retrievedIssue.key}`);
  } catch (error) {
    console.error(error.message);
  }
}

if (require.main === module) {
  main();
}