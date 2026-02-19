const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(apiToken) {
    this.apiToken = apiToken;
    this.baseURL = 'https://your-jira-instance.atlassian.net/rest/api/3';
  }

  async createIssue(summary, description) {
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary,
        description,
        issuetype: { name: 'Task' }
      }
    };

    try {
      const response = await axios.post(`${this.baseURL}/issue`, issueData, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      console.log('Issue created:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async getIssue(issueKey) {
    try {
      const response = await axios.get(`${this.baseURL}/issue/${issueKey}`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      console.log('Issue retrieved:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error retrieving issue:', error);
      throw error;
    }
  }

  async updateIssue(issueKey, summary, description) {
    const issueData = {
      fields: {
        summary,
        description
      }
    };

    try {
      const response = await axios.put(`${this.baseURL}/issue/${issueKey}`, issueData, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      console.log('Issue updated:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(`${this.baseURL}/issue/${issueKey}`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiToken}:x`).toString('base64')}`
        }
      });

      console.log('Issue deleted:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error deleting issue:', error);
      throw error;
    }
  }
}

class JavaScriptAgent {
  constructor(jiraClient, apiKey) {
    this.jiraClient = jiraClient;
    this.apiKey = apiKey;
  }

  async registerEvent(eventType, eventData) {
    const event = {
      type: eventType,
      data: eventData
    };

    try {
      const response = await axios.post(`${this.jiraClient.baseURL}/event`, event, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      console.log('Event registered:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error registering event:', error);
      throw error;
    }
  }

  async monitorActivity() {
    try {
      const response = await axios.get(`${this.jiraClient.baseURL}/activity`, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`
        }
      });

      console.log('Activity monitored:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error monitoring activity:', error);
      throw error;
    }
  }

  async main() {
    try {
      const apiKey = 'YOUR_JIRA_API_KEY';
      const jiraClient = new JiraClient(apiKey);
      const javascriptAgent = new JavaScriptAgent(jiraClient, apiKey);

      await javascriptAgent.registerEvent('activity', { eventType: 'start', eventData: 'Starting the activity monitor' });
      await javascriptAgent.monitorActivity();
    } catch (error) {
      console.error('Error:', error);
    }
  }
}

// Example usage
const apiKey = 'YOUR_JIRA_API_KEY';
const jiraClient = new JiraClient(apiKey);
const javascriptAgent = new JavaScriptAgent(jiraClient, apiKey);

javascriptAgent.main();