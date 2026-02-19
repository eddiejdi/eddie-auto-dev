const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(apiToken, baseUrl) {
    this.apiToken = apiToken;
    this.baseUrl = baseUrl;
  }

  async createIssue(summary, description) {
    const issueData = {
      fields: {
        project: {
          key: 'YOUR_PROJECT_KEY', // Substitua pelo código do projeto
        },
        summary,
        description,
        issuetype: {
          name: 'Bug',
        },
      },
    };

    try {
      const response = await axios.post(`${this.baseUrl}/rest/api/2/issue`, issueData, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.baseUrl}/rest/api/2/issue/${issueKey}`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`,
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey, summary, description) {
    const issueData = {
      fields: {
        summary,
        description,
      },
    };

    try {
      const response = await axios.put(`${this.baseUrl}/rest/api/2/issue/${issueKey}`, issueData, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`,
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(`${this.baseUrl}/rest/api/2/issue/${issueKey}`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`,
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

class JavaScriptAgent {
  constructor(apiToken, baseUrl) {
    this.jiraClient = new JiraClient(apiToken, baseUrl);
  }

  async trackActivity(issueKey, activityType, description) {
    const taskId = uuidv4();
    const taskData = {
      fields: {
        summary: `Task ${taskId}`,
        description,
        issuetype: {
          name: 'To Do',
        },
      },
    };

    try {
      await this.jiraClient.createIssue('JavaScript Agent Task', JSON.stringify(taskData));
      console.log(`Task created: ${taskId}`);

      const updateData = {
        fields: {
          status: {
            name: activityType,
          },
        },
      };

      await this.jiraClient.updateIssue(issueKey, 'JavaScript Agent Activity', JSON.stringify(updateData));
      console.log(`Activity updated: ${activityType}`);
    } catch (error) {
      throw new Error(`Failed to track activity: ${error.message}`);
    }
  }

  async main() {
    try {
      await this.trackActivity('YOUR_ISSUE_KEY', 'Completed', 'This is a completed task');
    } catch (error) {
      console.error(error);
    }
  }
}

const apiToken = process.env.JIRA_API_TOKEN;
const baseUrl = 'https://your-jira-instance.atlassian.net';

const agent = new JavaScriptAgent(apiToken, baseUrl);

agent.main();