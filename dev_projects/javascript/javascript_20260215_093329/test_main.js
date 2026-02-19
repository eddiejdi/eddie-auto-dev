const axios = require('axios');
const fs = require('fs');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssues(query) {
    const response = await axios.get(`${this.url}/rest/api/2/search`, {
      params: {
        jql: query,
        fields: 'summary,status',
      },
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
    });

    return response.data;
  }

  async logActivity(issueId, activity) {
    const response = await axios.post(`${this.url}/rest/api/2/issue/${issueId}/comment`, {
      body: activity,
    }, {
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
    });

    return response.data;
  }
}

class ScrumBoard {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async fetchIssues(query) {
    const issues = await this.jiraClient.getIssues(query);
    return issues;
  }

  async logActivity(issueId, activity) {
    await this.jiraClient.logActivity(issueId, activity);
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-url.com';
  const jiraToken = 'your-jira-token';
  const scrumBoard = new ScrumBoard(new JiraClient(jiraUrl, jiraToken));

  try {
    const query = 'project=YOUR_PROJECT_KEY AND status IN (TO_DO, IN_PROGRESS)';
    const issues = await scrumBoard.fetchIssues(query);

    console.log('Issues:', issues);

    // Log some activities
    await scrumBoard.logActivity(issues[0].id, 'This is a new task');
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}