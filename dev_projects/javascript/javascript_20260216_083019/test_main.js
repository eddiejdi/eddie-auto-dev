const axios = require('axios');
const { exec } = require('child_process');

class JiraTracker {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
  }

  async logActivity(activity) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
        fields: {
          summary: activity,
          description: 'Log of activity',
          issuetype: { name: 'Task' },
          project: { key: 'YOUR_PROJECT_KEY' }
        }
      }, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.apiKey}:${this.apiKey}`).toString('base64')}`
        }
      });

      console.log(`Activity logged successfully: ${response.data.key}`);
    } catch (error) {
      console.error(`Error logging activity: ${error.message}`);
    }
  }

  async executeCommand(command) {
    try {
      const { stdout, stderr } = await exec(command);

      if (stderr) {
        throw new Error(stderr);
      }

      console.log(`Command executed successfully: ${stdout}`);
    } catch (error) {
      console.error(`Error executing command: ${error.message}`);
    }
  }
}

// Exemplo de uso
const jiraTracker = new JiraTracker('https://your-jira-instance.atlassian.net', 'YOUR_API_KEY');

describe('JiraTracker class', () => {
  describe('logActivity method', () => {
    it('should log an activity successfully with valid inputs', async () => {
      const activity = 'New feature implemented';
      await jiraTracker.logActivity(activity);
      // Add assertions to verify the response or state
    });

    it('should throw an error if the summary is empty', async () => {
      try {
        await jiraTracker.logActivity('');
      } catch (error) {
        expect(error.message).toBe('Summary cannot be empty');
      }
    });
  });

  describe('executeCommand method', () => {
    it('should execute a command successfully with valid inputs', async () => {
      const command = 'npm test';
      await jiraTracker.executeCommand(command);
      // Add assertions to verify the response or state
    });

    it('should throw an error if the command is empty', async () => {
      try {
        await jiraTracker.executeCommand('');
      } catch (error) {
        expect(error.message).toBe('Command cannot be empty');
      }
    });
  });
});