const axios = require('axios');
const { expect } = require('chai');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async login(username, password) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/session`, {
      username,
      password,
    });
    return response.data.token;
  }

  async createIssue(projectKey, issueType, fields) {
    const token = await this.login(this.options.username, this.options.password);
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, {
      fields: {
        project: { key: projectKey },
        summary: fields.summary,
        description: fields.description,
        issuetype: { name: issueType },
      },
      token,
    });
    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login(this.options.username, this.options.password);
    const response = await axios.put(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, {
      fields: fields,
      token,
    });
    return response.data;
  }

  async getIssue(issueId) {
    const token = await this.login(this.options.username, this.options.password);
    const response = await axios.get(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, {
      token,
    });
    return response.data;
  }
}

describe('JiraClient', () => {
  describe('#login', () => {
    it('should return a token on successful login', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      const response = await jiraClient.login('your-username', 'your-password');
      expect(response).to.have.property('token');
    });

    it('should throw an error on invalid credentials', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'invalid-username', password: 'invalid-password' };
      const jiraClient = new JiraClient(options);
      await expect(jiraClient.login('invalid-username', 'invalid-password')).to.be.rejected;
    });
  });

  describe('#createIssue', () => {
    it('should return an issue ID on successful creation', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      const projectKey = 'YOUR_PROJECT_KEY';
      const issueType = 'Task';
      const fields = { summary: 'Implement Jira Agent integration', description: 'Track project activities' };
      const response = await jiraClient.createIssue(projectKey, issueType, fields);
      expect(response).to.have.property('id');
    });

    it('should throw an error on invalid input', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      await expect(jiraClient.createIssue('invalid-project-key', 'Task', {})).to.be.rejected;
    });
  });

  describe('#updateIssue', () => {
    it('should return an updated issue on successful update', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      const projectKey = 'YOUR_PROJECT_KEY';
      const issueType = 'Task';
      const fields = { summary: 'Implement Jira Agent integration', description: 'Track project activities' };
      const response = await jiraClient.createIssue(projectKey, issueType, fields);
      const updatedFields = { status: { name: 'In Progress' } };
      const response = await jiraClient.updateIssue(response.id, updatedFields);
      expect(response).to.have.property('id');
    });

    it('should throw an error on invalid input', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      await expect(jiraClient.updateIssue('invalid-issue-id', {})).to.be.rejected;
    });
  });

  describe('#getIssue', () => {
    it('should return an issue on successful retrieval', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      const projectKey = 'YOUR_PROJECT_KEY';
      const issueType = 'Task';
      const fields = { summary: 'Implement Jira Agent integration', description: 'Track project activities' };
      const response = await jiraClient.createIssue(projectKey, issueType, fields);
      const retrievedIssue = await jiraClient.getIssue(response.id);
      expect(retrievedIssue).to.have.property('id');
    });

    it('should throw an error on invalid input', async () => {
      const options = { baseUrl: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' };
      const jiraClient = new JiraClient(options);
      await expect(jiraClient.getIssue('invalid-issue-id')).to.be.rejected;
    });
  });
});