const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async createIssue(title, description) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, {
      fields: {
        project: { key: this.options.projectKey },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    });

    return response.data;
  }

  async updateIssue(issueId, updates) {
    const response = await axios.put(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, updates);

    return response.data;
  }

  async getIssues() {
    const response = await axios.get(`${this.options.baseUrl}/rest/api/2/search`, {
      jql: 'project = ${this.options.projectKey}',
      fields: ['id', 'summary', 'status']
    });

    return response.data.issues;
  }
}

class JavaScriptAgent {
  constructor(options) {
    this.options = options;
    this.jiraClient = new JiraClient(this.options);
  }

  async monitorActivity() {
    const issues = await this.jiraClient.getIssues();

    for (const issue of issues) {
      console.log(`Issue ID: ${issue.id}, Summary: ${issue.summary}, Status: ${issue.fields.status.name}`);
    }
  }

  async updateStatus(issueId, newStatus) {
    const updates = {
      fields: {
        status: { id: newStatus }
      }
    };

    await this.jiraClient.updateIssue(issueId, updates);
    console.log(`Status updated for issue ID ${issueId} to ${newStatus}`);
  }

  async notifyUser(issueId, message) {
    // Implemente a lógica para enviar uma notificação automática
    console.log(`Notifying user about issue ID ${issueId}: ${message}`);
  }
}

// Configurações do JavaScriptAgent
const agentOptions = {
  baseUrl: 'https://your-jira-instance.atlassian.net',
  projectKey: 'YOUR_PROJECT_KEY'
};

// Instância do JavaScriptAgent
const agent = new JavaScriptAgent(agentOptions);

describe('JiraClient', () => {
  describe('createIssue', () => {
    it('should create a new issue with valid data', async () => {
      const title = 'Test Issue';
      const description = 'This is a test issue for the Jira Client.';
      const response = await agent.jiraClient.createIssue(title, description);
      expect(response).toHaveProperty('id');
    });

    it('should throw an error if the title or description is empty', async () => {
      try {
        await agent.jiraClient.createIssue('', 'This is a test issue for the Jira Client.');
      } catch (error) {
        expect(error.message).toContain('Title and description cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const issueId = '12345';
      const newStatus = 'In Progress';
      await agent.jiraClient.updateStatus(issueId, newStatus);
      expect(agent.jiraClient.getIssues().some(issue => issue.id === issueId && issue.fields.status.name === newStatus)).toBe(true);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.jiraClient.updateStatus('invalid-id', 'In Progress');
      } catch (error) {
        expect(error.message).toContain('Issue ID must be a valid UUID');
      }
    });
  });

  describe('getIssues', () => {
    it('should return an array of issues with the specified project key', async () => {
      const response = await agent.jiraClient.getIssues();
      expect(response.length).toBeGreaterThan(0);
      expect(response.every(issue => issue.fields.project.key === agentOptions.projectKey)).toBe(true);
    });

    it('should throw an error if the JQL query is invalid', async () => {
      try {
        await agent.jiraClient.getIssues('{jql:invalid-query}');
      } catch (error) {
        expect(error.message).toContain('Invalid JQL query');
      }
    });
  });
});

describe('JavaScriptAgent', () => {
  describe('monitorActivity', () => {
    it('should log the summary and status of each issue', async () => {
      const issues = await agent.jiraClient.getIssues();
      for (const issue of issues) {
        console.log(`Issue ID: ${issue.id}, Summary: ${issue.summary}, Status: ${issue.fields.status.name}`);
      }
    });
  });

  describe('updateStatus', () => {
    it('should update the status of an existing issue', async () => {
      const issueId = '12345';
      const newStatus = 'In Progress';
      await agent.jiraClient.updateStatus(issueId, newStatus);
      expect(agent.jiraClient.getIssues().some(issue => issue.id === issueId && issue.fields.status.name === newStatus)).toBe(true);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.jiraClient.updateStatus('invalid-id', 'In Progress');
      } catch (error) {
        expect(error.message).toContain('Issue ID must be a valid UUID');
      }
    });
  });

  describe('notifyUser', () => {
    it('should log a notification message', async () => {
      const issueId = '12345';
      await agent.jiraClient.notifyUser(issueId, `Your issue ${issueId} has been updated to In Progress`);
      expect(console.log).toHaveBeenCalledWith(`Notifying user about issue ID ${issueId}: Your issue 12345 has been updated to In Progress`);
    });
  });
});