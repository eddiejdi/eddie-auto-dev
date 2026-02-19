const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

class JiraScrumb {
  constructor(options) {
    this.jiraClient = new JiraClient(options);
  }

  async login() {
    const response = await this.jiraClient.login();
    return response;
  }

  async createIssue(title, description) {
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    };

    const response = await this.jiraClient.createIssue(issueData);
    return response;
  }

  async updateIssue(id, fields) {
    const issueData = {
      fields
    };

    const response = await this.jiraClient.updateIssue(id, issueData);
    return response;
  }

  async getIssues() {
    const issues = await this.jiraClient.getIssues();
    return issues;
  }
}

async function main() {
  try {
    const options = {
      username: 'YOUR_USERNAME',
      password: 'YOUR_PASSWORD',
      server: 'https://your-jira-server.atlassian.net'
    };

    const jiraScrumb = new JiraScrumb(options);

    await jiraScrumb.login();

    const title = 'New Bug Report';
    const description = 'This is a new bug report for testing purposes.';
    const issue = await jiraScrumb.createIssue(title, description);
    console.log('Created Issue:', issue.id);

    const updatedFields = {
      status: { name: 'In Progress' }
    };
    await jiraScrumb.updateIssue(issue.id, updatedFields);
    console.log('Updated Issue Status:', issue.fields.status.name);

    const issues = await jiraScrumb.getIssues();
    console.log('All Issues:', issues.map(issue => issue.key));

  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}