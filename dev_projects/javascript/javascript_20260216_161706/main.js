const axios = require('axios');
const fs = require('fs');

class JiraClient {
  constructor(apiKey, serverUrl) {
    this.apiKey = apiKey;
    this.serverUrl = serverUrl;
  }

  async getIssue(issueId) {
    const url = `${this.serverUrl}/rest/api/2/issue/${issueId}`;
    const headers = { 'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}` };
    try {
      const response = await axios.get(url, { headers });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get issue: ${issueId}`, error);
    }
  }

  async logEvent(issueId, event) {
    const url = `${this.serverUrl}/rest/api/2/issue/${issueId}/comment`;
    const headers = { 'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}` };
    try {
      await axios.post(url, { body: event }, { headers });
      console.log(`Event logged for issue ${issueId}`);
    } catch (error) {
      throw new Error(`Failed to log event for issue ${issueId}`, error);
    }
  }

  async monitorEvents(issueId) {
    const interval = 5000; // Check every 5 seconds
    setInterval(async () => {
      try {
        const issue = await this.getIssue(issueId);
        console.log(`Monitoring issue ${issueId}:`, issue.fields.summary);
        if (issue.fields.status.name === 'Closed') {
          console.log('Issue closed, logging event...');
          await this.logEvent(issueId, 'Issue resolved');
        }
      } catch (error) {
        console.error(`Error monitoring issue ${issueId}`, error);
      }
    }, interval);
  }
}

async function main() {
  const apiKey = 'your-jira-api-key';
  const serverUrl = 'https://your-jira-server.com';
  const issueId = 'ABC-123';

  const jiraClient = new JiraClient(apiKey, serverUrl);

  try {
    await jiraClient.monitorEvents(issueId);
  } catch (error) {
    console.error('Error monitoring events:', error);
  }
}

if (require.main === module) {
  main();
}