const axios = require('axios');

class JiraClient {
  constructor(apiKey, serverUrl) {
    this.apiKey = apiKey;
    this.serverUrl = serverUrl;
  }

  async getIssues() {
    const response = await axios.get(`${this.serverUrl}/rest/api/2/search`, {
      params: {
        jql: 'project = MyProject',
        fields: ['summary', 'status'],
      },
      headers: {
        'Authorization': `Basic ${Buffer.from(`${this.apiKey}:`).toString('base64')}`,
      },
    });

    return response.data.issues;
  }

  async createIssue(summary, description) {
    const response = await axios.post(`${this.serverUrl}/rest/api/2/issue`, {
      fields: {
        project: { key: 'MyProject' },
        summary,
        description,
        status: { name: 'Open' },
      },
    });

    return response.data;
  }
}

async function main() {
  const apiKey = 'your-api-key';
  const serverUrl = 'https://your-jira-server.com';

  const jiraClient = new JiraClient(apiKey, serverUrl);

  try {
    const issues = await jiraClient.getIssues();
    console.log('Issues:', issues);

    const summary = 'New JavaScript Activity';
    const description = 'This is a new JavaScript activity tracked in Jira.';
    const issue = await jiraClient.createIssue(summary, description);
    console.log('Created Issue:', issue);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}