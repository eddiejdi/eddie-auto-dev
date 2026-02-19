const axios = require('axios');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async login(username, password) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/session`, { username, password });
    return response.data;
  }

  async createIssue(projectKey, issueType, fields) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, {
      project: { key: projectKey },
      issuetype: { name: issueType },
      fields
    }, this.options.headers);
    return response.data;
  }
}

const options = {
  baseUrl: 'https://your-jira-instance.atlassian.net',
  headers: {
    'Authorization': `Basic ${Buffer.from(`${options.username}:${options.password}`).toString('base64')}`
  }
};

describe('JiraClient', () => {
  describe('login', () => {
    it('should return login response with valid credentials', async () => {
      const jiraClient = new JiraClient(options);
      const username = 'your-username';
      const password = 'your-password';

      try {
        const loginResponse = await jiraClient.login(username, password);
        expect(loginResponse).toHaveProperty('session');
        expect(loginResponse.session).toHaveProperty('name', username);
      } catch (error) {
        console.error('Error:', error.message);
        fail();
      }
    });

    it('should throw an error with invalid credentials', async () => {
      const jiraClient = new JiraClient(options);
      const username = 'your-username';
      const password = 'invalid-password';

      try {
        await jiraClient.login(username, password);
        fail();
      } catch (error) {
        expect(error.message).toContain('Invalid credentials');
      }
    });
  });

  describe('createIssue', () => {
    it('should return issue response with valid fields', async () => {
      const jiraClient = new JiraClient(options);
      const projectKey = 'YOUR-PROJECT-KEY';
      const issueType = 'Bug';
      const issueFields = {
        summary: 'Test Issue',
        description: 'This is a test issue created using JavaScript Agent with Jira.',
        priority: { name: 'High' },
        assignee: { id: 'assignee-id' }
      };

      try {
        const issueResponse = await jiraClient.createIssue(projectKey, issueType, issueFields);
        expect(issueResponse).toHaveProperty('id');
        expect(issueResponse.id).toBeTruthy();
      } catch (error) {
        console.error('Error:', error.message);
        fail();
      }
    });

    it('should throw an error with invalid fields', async () => {
      const jiraClient = new JiraClient(options);
      const projectKey = 'YOUR-PROJECT-KEY';
      const issueType = 'Bug';
      const issueFields = {};

      try {
        await jiraClient.createIssue(projectKey, issueType, issueFields);
        fail();
      } catch (error) {
        expect(error.message).toContain('Invalid fields');
      }
    });
  });
});