const axios = require('axios');
const { exec } = require('child_process');

class JiraIntegration {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
  }

  async trackActivity(activity) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, activity, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:`).toString('base64')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(`Activity tracked successfully: ${response.data.key}`);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }

  async executeCommand(command) {
    try {
      const { stdout, stderr } = await exec(command);

      if (stderr) {
        throw new Error(stderr.toString());
      }

      console.log(`Command executed successfully: ${stdout}`);
    } catch (error) {
      console.error('Error executing command:', error);
    }
  }
}

// Example usage
const jiraIntegration = new JiraIntegration('https://your-jira-instance.atlassian.net', 'your-api-key');

async function main() {
  const activity = {
    fields: {
      summary: 'New issue created',
      description: 'This is a test issue'
    }
  };

  await jiraIntegration.trackActivity(activity);

  const command = 'echo "Hello, Jira!"';
  await jiraIntegration.executeCommand(command);
}

main();