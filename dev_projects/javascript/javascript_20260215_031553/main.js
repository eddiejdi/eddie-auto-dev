const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(apiToken, baseUrl) {
    this.apiToken = apiToken;
    this.baseUrl = baseUrl;
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
      const response = await axios.post(`${this.baseUrl}/rest/api/2/issue`, issueData, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
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
      const response = await axios.put(`${this.baseUrl}/rest/api/2/issue/${issueKey}`, issueData, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.baseUrl}/rest/api/2/issue/${issueKey}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error getting issue:', error);
      throw error;
    }
  }
}

class JavaScriptAgent {
  constructor(apiToken, baseUrl) {
    this.jiraClient = new JiraClient(apiToken, baseUrl);
  }

  async trackActivity(title, description) {
    const issueKey = uuidv4();
    await this.jiraClient.createIssue(title, description);

    return issueKey;
  }

  async updateActivity(issueKey, title, description) {
    await this.jiraClient.updateIssue(issueKey, title, description);
  }

  async getActivity(issueKey) {
    return this.jiraClient.getIssue(issueKey);
  }
}

async function main() {
  const apiToken = 'YOUR_JIRA_API_TOKEN';
  const baseUrl = 'https://your-jira-instance.atlassian.net/rest/api/2';

  const agent = new JavaScriptAgent(apiToken, baseUrl);

  try {
    const issueKey = await agent.trackActivity('New Task', 'This is a new task.');
    console.log(`Issue created with key: ${issueKey}`);

    const updatedTitle = 'Updated Task';
    const updatedDescription = 'This task has been updated.';
    await agent.updateActivity(issueKey, updatedTitle, updatedDescription);
    console.log(`Issue updated with key: ${issueKey}`);

    const activity = await agent.getActivity(issueKey);
    console.log('Issue details:', activity);

  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}