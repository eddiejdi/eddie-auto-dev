const axios = require('axios');

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

  async getIssues(status) {
    const response = await axios.get(`${this.options.baseUrl}/rest/api/2/search`, {
      jql: `status = ${status}`,
      fields: ['id', 'summary']
    });

    return response.data.items.map(issue => ({
      id: issue.id,
      summary: issue.fields.summary
    }));
  }
}

const options = {
  baseUrl: 'https://your-jira-instance.atlassian.net',
  projectKey: 'YOUR-PROJECT-KEY'
};

async function main() {
  const client = new JiraClient(options);

  try {
    const issue = await client.createIssue('New Bug', 'This is a new bug report.');
    console.log(`Created Issue ID: ${issue.id}`);

    const updates = { status: 'In Progress' };
    await client.updateIssue(issue.id, updates);
    console.log(`Updated Issue Status to In Progress`);

    const issues = await client.getIssues('Open');
    console.log('Open Issues:');
    issues.forEach(issue => console.log(`${issue.id}: ${issue.summary}`));
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}