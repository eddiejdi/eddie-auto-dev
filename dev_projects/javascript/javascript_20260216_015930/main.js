// Import necessary libraries and modules
const axios = require('axios');
const { exec } = require('child_process');

// Define the JavaScript Agent class
class JavaScriptAgent {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
  }

  // Method to track an activity in Jira
  async trackActivity(issueId, activityDescription) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue/${issueId}/worklog`, {
        comment: {
          body: activityDescription,
        },
        started: new Date().toISOString(),
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      console.log(`Activity tracked successfully:`, response.data);
    } catch (error) {
      console.error(`Error tracking activity:`, error);
    }
  }

  // Method to execute a command in the system
  async executeCommand(command) {
    try {
      const { stdout, stderr } = await exec(command);

      if (stderr) {
        throw new Error(stderr.toString());
      }

      console.log(`Command executed successfully:`, stdout.toString());
    } catch (error) {
      console.error(`Error executing command:`, error);
    }
  }
}

// Example usage
(async () => {
  const agent = new JavaScriptAgent('https://your-jira-instance.atlassian.net', 'your-api-key');

  // Track an activity in Jira
  await agent.trackActivity('JIRA-123', 'Completed the task');

  // Execute a command in the system
  await agent.executeCommand('ls -l');
})();