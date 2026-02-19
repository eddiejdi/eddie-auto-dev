const axios = require('axios');

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

// Example usage
const jiraClient = new JiraClient({
  baseUrl: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password',
});

(async () => {
  try {
    const issueId = await jiraClient.createIssue('YOUR_PROJECT_KEY', 'Task', { summary: 'Implement Jira Agent integration', description: 'Track project activities' });
    console.log(`Created issue with ID ${issueId}`);

    const updatedFields = { status: { name: 'In Progress' } };
    await jiraClient.updateIssue(issueId, updatedFields);
    console.log(`Updated issue with ID ${issueId}`);

    const issue = await jiraClient.getIssue(issueId);
    console.log(`Retrieved issue:`, issue);

  } catch (error) {
    console.error('Error:', error);
  }
})();