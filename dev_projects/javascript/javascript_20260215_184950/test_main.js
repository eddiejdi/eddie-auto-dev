const axios = require('axios');

class JavaScriptAgent {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
  }

  async sendActivity(activity) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, activity, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(`Activity sent successfully: ${response.data}`);
    } catch (error) {
      console.error('Error sending activity:', error);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const apiKey = 'your-api-key';

  const agent = new JavaScriptAgent(jiraUrl, apiKey);

  const activity = {
    fields: {
      project: { key: 'YOUR-PROJECT-KEY' },
      summary: 'Example Activity',
      description: 'This is an example activity sent from the JavaScript Agent.',
      issuetype: { name: 'Bug' }
    }
  };

  await agent.sendActivity(activity);
}

if (require.main === module) {
  main();
}