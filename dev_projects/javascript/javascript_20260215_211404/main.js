const axios = require('axios');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssue(issueKey) {
    const response = await axios.get(`${this.url}/rest/api/2/issue/${issueKey}`, {
      headers: {
        'Authorization': `Basic ${Buffer.from(`${this.token}:`).toString('base64')}`,
      },
    });

    return response.data;
  }

  async updateIssue(issueKey, data) {
    const response = await axios.put(`${this.url}/rest/api/2/issue/${issueKey}`, data, {
      headers: {
        'Authorization': `Basic ${Buffer.from(`${this.token}:`).toString('base64')}`,
      },
    });

    return response.data;
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-api-token');

  try {
    const issue = await jiraClient.getIssue('JIRA-123');
    console.log(issue);

    const updatedData = {
      fields: {
        status: {
          name: 'In Progress',
        },
      },
    };

    await jiraClient.updateIssue('JIRA-123', updatedData);
    console.log('Issue updated successfully.');
  } catch (error) {
    console.error('Error:', error.message);
  }
}

if (require.main === module) {
  main();
}