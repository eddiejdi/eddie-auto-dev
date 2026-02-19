// Importações necessárias
const axios = require('axios');

class JavaScriptAgent {
  constructor(jiraUrl, token) {
    this.jiraUrl = jiraUrl;
    this.token = token;
  }

  async trackActivity(issueKey, activityType, description) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue/${issueKey}/worklog`, {
        fields: {
          worklog: {
            comments: [
              {
                author: {
                  name: 'JavaScript Agent',
                  email: 'javascriptagent@example.com'
                },
                body: description
              }
            ],
            type: activityType,
            started: new Date().toISOString()
          }
        }
      }, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:`).toString('base64')}`
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }
}

// Função principal para execução do script
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const token = 'your-api-token';

  const agent = new JavaScriptAgent(jiraUrl, token);

  try {
    await agent.trackActivity('ABC-123', 'Task Completed', 'The task was completed successfully.');
  } catch (error) {
    console.error(error);
  }
}

// Execução do script se for CLI
if (require.main === module) {
  main();
}