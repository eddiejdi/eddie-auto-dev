const axios = require('axios');
const { exec } = require('child_process');

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async createIssue(title, description) {
    const response = await axios.post(`${this.options.baseUrl}/rest/api/2/issue`, {
      fields: {
        project: {
          key: this.options.projectKey
        },
        summary: title,
        description: description,
        issuetype: {
          name: 'Bug'
        }
      }
    });

    return response.data;
  }

  async updateIssue(issueId, title, description) {
    const response = await axios.put(`${this.options.baseUrl}/rest/api/2/issue/${issueId}`, {
      fields: {
        summary: title,
        description: description
      }
    });

    return response.data;
  }

  async getIssues(projectKey) {
    const response = await axios.get(`${this.options.baseUrl}/rest/api/2/search`, {
      jql: `project=${projectKey} AND status!=closed`
    });

    return response.data.issues;
  }
}

class Logger {
  constructor(options) {
    this.options = options;
  }

  log(message) {
    console.log(`[${new Date().toISOString()}] ${message}`);
  }
}

class ProjectManager {
  constructor(options) {
    this.options = options;
    this.jiraClient = new JiraClient(this.options);
    this.logger = new Logger(this.options);
  }

  async startProject(projectKey) {
    const issues = await this.jiraClient.getIssues(projectKey);
    for (const issue of issues) {
      await this.updateIssue(issue.id, `Updated by Project Manager`, `${issue.summary} - Updated`);
      this.logger.log(`Updated issue ${issue.key}`);
    }
  }

  async stopProject(projectKey) {
    const issues = await this.jiraClient.getIssues(projectKey);
    for (const issue of issues) {
      await this.updateIssue(issue.id, `Stopped by Project Manager`, `${issue.summary} - Stopped`);
      this.logger.log(`Stopped issue ${issue.key}`);
    }
  }

  async main() {
    const projectKey = 'YOUR_PROJECT_KEY';
    await this.startProject(projectKey);
    // Add more logic to stop the project
  }
}

if (require.main === module) {
  const options = {
    baseUrl: 'https://your-jira-instance.atlassian.net',
    projectKey: 'YOUR_PROJECT_KEY'
  };
  const projectManager = new ProjectManager(options);
  projectManager.main();
}