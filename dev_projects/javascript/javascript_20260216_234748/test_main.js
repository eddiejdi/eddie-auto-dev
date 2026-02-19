const axios = require('axios');
const { JiraClient } = require('@jira/client');

class JavaScriptAgent {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
    this.client = new JiraClient({ url: this.jiraUrl });
  }

  async createIssue(title, description, projectKey) {
    try {
      const issueData = {
        fields: {
          project: { key: projectKey },
          summary: title,
          description: description,
          issuetype: { name: 'Bug' }
        }
      };

      await this.client.createIssue(issueData);
      console.log('Issue created successfully');
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async updateIssue(id, title, description) {
    try {
      const issueData = {
        fields: {
          summary: title,
          description: description
        }
      };

      await this.client.updateIssue(id, issueData);
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(id) {
    try {
      await this.client.deleteIssue(id);
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new JavaScriptAgent(jiraUrl, username, password);

  try {
    await agent.createIssue('Test Issue', 'This is a test issue.', 'YOUR-PROJECT-KEY');
    await agent.updateIssue(12345, 'Updated Test Issue', 'This is an updated test issue.');
    await agent.deleteIssue(12345);
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}