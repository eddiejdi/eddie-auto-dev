// Importações necessárias
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssue(issueId) {
    const response = await axios.get(`${this.url}/rest/api/2/issue/${issueId}`, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
      },
    });

    return response.data;
  }
}

class ActivityTracker {
  constructor(jiraClient, issueId) {
    this.jiraClient = jiraClient;
    this.issueId = issueId;
    this.activities = [];
  }

  async trackActivity() {
    try {
      const issue = await this.jiraClient.getIssue(this.issueId);
      this.activities.push({
        id: uuidv4(),
        timestamp: new Date().toISOString(),
        description: issue.fields.summary,
      });

      console.log(`Tracking activity for issue ${this.issueId}`);
    } catch (error) {
      console.error('Error tracking activity:', error.message);
    }
  }

  async monitorActivity() {
    const interval = setInterval(async () => {
      try {
        await this.trackActivity();
      } catch (error) {
        console.error('Error monitoring activity:', error.message);
      }
    }, 60000); // Monitorar cada minuto

    return () => clearInterval(interval);
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const jiraToken = 'your-jira-token';
  const issueId = 'ABC-123';

  const jiraClient = new JiraClient(jiraUrl, jiraToken);
  const activityTracker = new ActivityTracker(jiraClient, issueId);

  await activityTracker.monitorActivity();

  console.log('Activity tracking started');
}

if (require.main === module) {
  main();
}