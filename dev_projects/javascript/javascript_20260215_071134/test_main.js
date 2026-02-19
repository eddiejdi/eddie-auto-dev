const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(token) {
    this.token = token;
    this.baseURL = 'https://your-jira-instance.atlassian.net/rest/api/3';
  }

  async getIssues(query) {
    try {
      const response = await axios.get(`${this.baseURL}/search`, {
        params: { jql: query, fields: ['key', 'summary'] },
        headers: { Authorization: `Bearer ${this.token}` }
      });
      return response.data.items;
    } catch (error) {
      console.error('Error fetching issues:', error);
      throw error;
    }
  }

  async createIssue(summary, description) {
    try {
      const issue = {
        fields: {
          summary,
          description
        }
      };
      const response = await axios.post(`${this.baseURL}/issue`, issue, {
        headers: { Authorization: `Bearer ${this.token}` }
      });
      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(issueKey, summary, description) {
    try {
      const issue = {
        fields: {
          summary,
          description
        }
      };
      const response = await axios.put(`${this.baseURL}/issue/${issueKey}`, issue, {
        headers: { Authorization: `Bearer ${this.token}` }
      });
      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueKey) {
    try {
      const response = await axios.delete(`${this.baseURL}/issue/${issueKey}`, {
        headers: { Authorization: `Bearer ${this.token}` }
      });
      return response.data;
    } catch (error) {
      console.error('Error deleting issue:', error);
      throw error;
    }
  }
}

class JavaScriptAgent {
  constructor(token, jiraClient) {
    this.token = token;
    this.jiraClient = jiraClient;
  }

  async monitorActivity() {
    try {
      const issues = await this.jiraClient.getIssues('status=Open');
      for (const issue of issues) {
        console.log(`Issue ${issue.key}: ${issue.summary}`);
        await this.updateIssue(issue.key, 'Status updated', `Updated by JavaScript Agent`);
      }
    } catch (error) {
      console.error('Error monitoring activity:', error);
    }
  }

  async registerEvent(eventType, eventData) {
    try {
      const event = {
        type: eventType,
        data: eventData
      };
      await this.jiraClient.createIssue('JavaScriptAgent Event', JSON.stringify(event));
    } catch (error) {
      console.error('Error registering event:', error);
    }
  }

  async main() {
    try {
      // Simulação de atividades em JavaScript
      setTimeout(() => {
        this.registerEvent('ActivityUpdate', 'New task added');
      }, 2000);

      setInterval(() => {
        this.monitorActivity();
      }, 60000);
    } catch (error) {
      console.error('Error in main:', error);
    }
  }
}

// Função principal
async function main() {
  const token = 'your-jira-token';
  const jiraClient = new JiraClient(token);
  const agent = new JavaScriptAgent(token, jiraClient);

  await agent.main();
}

main().catch(error => console.error('Error:', error));