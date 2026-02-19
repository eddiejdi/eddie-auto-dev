const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(apiKey, username) {
    this.apiKey = apiKey;
    this.username = username;
    this.baseUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  }

  async createIssue(projectId, issueType, fields) {
    try {
      const response = await axios.post(`${this.baseUrl}/issue`, {
        project: { key: projectId },
        issuetype: { name: issueType },
        fields,
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.username}:${this.apiKey}`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueId, fields) {
    try {
      const response = await axios.put(`${this.baseUrl}/issue/${issueId}`, fields, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.username}:${this.apiKey}`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.baseUrl}/issue/${issueId}`, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.username}:${this.apiKey}`).toString('base64')}`,
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${error.message}`);
    }
  }

  async createComment(issueId, commentBody) {
    try {
      const response = await axios.post(`${this.baseUrl}/issue/${issueId}/comment`, {
        body: commentBody,
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.username}:${this.apiKey}`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create comment: ${error.message}`);
    }
  }

  async sendNotification(issueId, notificationType, message) {
    try {
      const response = await axios.post(`${this.baseUrl}/notification`, {
        issue: { id: issueId },
        type: notificationType,
        body: message,
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.username}:${this.apiKey}`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to send notification: ${error.message}`);
    }
  }
}

class JavaScriptAgent {
  constructor(apiKey, username) {
    this.jiraClient = new JiraClient(apiKey, username);
  }

  async main() {
    try {
      const projectId = 'YOUR_PROJECT_ID';
      const issueType = 'TASK';
      const fields = {
        summary: 'New task',
        description: 'This is a new task created by JavaScript Agent',
      };

      // Caso de sucesso com valores válidos
      await this.jiraClient.createIssue(projectId, issueType, fields);
      console.log('Issue created:', fields.summary);

      // Caso de erro (divisão por zero)
      const invalidFields = { summary: 'New task', description: 'This is a new task created by JavaScript Agent' };
      try {
        await this.jiraClient.createIssue(projectId, issueType, invalidFields);
      } catch (error) {
        console.error('Error:', error.message); // Expectation: Error: Failed to create issue: Division by zero
      }

      // Caso de erro (valores inválidos)
      const invalidSummary = { summary: '', description: 'This is a new task created by JavaScript Agent' };
      try {
        await this.jiraClient.createIssue(projectId, issueType, invalidSummary);
      } catch (error) {
        console.error('Error:', error.message); // Expectation: Error: Failed to create issue: Invalid summary
      }

      // Caso de sucesso com valores válidos
      const updatedFields = { status: { name: 'In Progress' } };
      await this.jiraClient.updateIssue(fields.summary, updatedFields);
      console.log('Status updated:', fields.status.name);

      // Caso de erro (valores inválidos)
      try {
        await this.jiraClient.updateIssue(fields.summary, invalidFields);
      } catch (error) {
        console.error('Error:', error.message); // Expectation: Error: Failed to update issue: Invalid status
      }

      // Caso de sucesso com valores válidos
      const commentBody = 'This is a comment from JavaScript Agent';
      await this.jiraClient.createComment(fields.summary, commentBody);
      console.log('Comment added:', commentBody);

      // Caso de erro (valores inválidos)
      try {
        await this.jiraClient.createComment(fields.summary, invalidSummary);
      } catch (error) {
        console.error('Error:', error.message); // Expectation: Error: Failed to create comment: Invalid body
      }

      // Caso de sucesso com valores válidos
      const notificationType = 'EMAIL';
      const message = 'This is a notification from JavaScript Agent';
      await this.jiraClient.sendNotification(fields.summary, notificationType, message);
      console.log('Notification sent:', message);

      // Caso de erro (valores inválidos)
      try {
        await this.jiraClient.sendNotification(fields.summary, invalidSummary, message);
      } catch (error) {
        console.error('Error:', error.message); // Expectation: Error: Failed to send notification: Invalid type
      }
    } catch (error) {
      console.error('Error:', error.message);
    }
  }
}

// Execução do programa
const apiKey = 'YOUR_JIRA_API_KEY';
const username = 'YOUR_JIRA_USERNAME';
const agent = new JavaScriptAgent(apiKey, username);
agent.main();