// Import necessary libraries and modules
const axios = require('axios');
const fs = require('fs');

// Define the JavaScript Agent class
class JavaScriptAgent {
  constructor(options) {
    this.options = options;
    this.jiraUrl = options.jiraUrl;
    this.username = options.username;
    this.password = options.password;
    this.projectKey = options.projectKey;
  }

  async fetchActivityLogs() {
    try {
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/search?jql=project=${this.projectKey}&fields=id,summary,status`);
      return response.data.results.map(result => ({
        id: result.id,
        summary: result.fields.summary,
        status: result.fields.status.name
      }));
    } catch (error) {
      throw new Error('Failed to fetch activity logs', error);
    }
  }

  async trackActivity(logs) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue/${logs[0].id}/comment`, {
        body: `Tracking of ${logs.map(log => log.summary).join(', ')}`
      }, {
        auth: {
          username: this.username,
          password: this.password
        }
      });
      return response.data;
    } catch (error) {
      throw new Error('Failed to track activity', error);
    }
  }

  async run() {
    try {
      const logs = await this.fetchActivityLogs();
      if (logs.length > 0) {
        const trackedResponse = await this.trackActivity(logs);
        console.log(`Tracked: ${trackedResponse}`);
      } else {
        console.log('No activity logs found');
      }
    } catch (error) {
      console.error(error.message);
    }
  }

  static main() {
    const agent = new JavaScriptAgent({
      jiraUrl: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password',
      projectKey: 'YOUR-PROJECT-KEY'
    });

    agent.run();
  }
}

// Execute the main function if this file is run as a script
if (require.main === module) {
  JavaScriptAgent.main();
}