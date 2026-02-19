const axios = require('axios');
const { JiraClient } = require('@atlassian/node-jira');

class JiraAgent {
  constructor(jiraToken, jiraUrl) {
    this.jiraToken = jiraToken;
    this.jiraUrl = jiraUrl;
    this.client = new JiraClient({ auth: this.jiraToken });
  }

  async createIssue(title, description) {
    try {
      const issue = await this.client.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description
        }
      });

      console.log('Issue created:', issue);
      return issue;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(issueId, title, description) {
    try {
      const updatedIssue = await this.client.updateIssue({
        fields: {
          summary: title,
          description: description
        },
        issueKey: issueId
      });

      console.log('Issue updated:', updatedIssue);
      return updatedIssue;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueId) {
    try {
      const deletedIssue = await this.client.deleteIssue({
        issueKey: issueId
      });

      console.log('Issue deleted:', deletedIssue);
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

async function main() {
  const jiraToken = 'YOUR_JIRA_TOKEN';
  const jiraUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  const agent = new JiraAgent(jiraToken, jiraUrl);

  try {
    await agent.createIssue('Test Issue', 'This is a test issue created by the JavaScript Agent.');
    // Add more operations as needed
  } catch (error) {
    console.error('Error executing main function:', error);
  }
}

if (require.main === module) {
  main();
}