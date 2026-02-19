// Importações necessárias
const axios = require('axios');
const { exec } = require('child_process');

class JavaScriptAgent {
  constructor(jiraUrl, token) {
    this.jiraUrl = jiraUrl;
    this.token = token;
  }

  async trackActivity(activity) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
        fields: {
          summary: activity.title,
          description: activity.description,
          priority: { name: 'High' },
          status: { name: 'In Progress' }
        }
      }, {
        headers: {
          Authorization: `Bearer ${this.token}`
        }
      });

      console.log('Activity tracked successfully:', response.data);
    } catch (error) {
      console.error('Error tracking activity:', error.message);
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
      console.error('Error executing command:', error.message);
    }
  }
}

// Exemplo de uso
const agent = new JavaScriptAgent('https://your-jira-instance.atlassian.net', 'your-api-token');

async function main() {
  try {
    await agent.trackActivity({
      title: 'Implement JavaScript Agent with Jira',
      description: 'This is a test to track activities in Jira using the JavaScript Agent.'
    });

    await agent.executeCommand('node your-script.js');
  } catch (error) {
    console.error(error);
  }
}

if (require.main === module) {
  main();
}