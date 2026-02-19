const axios = require('axios');
const { createLogger } = require('winston');

// Configuração do logger
const logger = createLogger({
  level: 'info',
  format: {
    timestamp: true,
    colorize: true,
    json: false,
    prettyPrint: true,
  },
});

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async login() {
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/session`, {
      username: this.username,
      password: this.password,
    });
    return response.data.sessionId;
  }

  async createIssue(issueData) {
    const sessionId = await this.login();
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
      fields: issueData,
      session: { id: sessionId },
    });
    return response.data.issue.key;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async monitorEvents() {
    try {
      const sessionId = await this.jiraClient.login();
      logger.info('Logged in as Jira user');

      // Simulação de eventos
      for (let i = 0; i < 10; i++) {
        const issueData = {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: `Event ${i}`,
          description: `This is a test event ${i}`,
          issuetype: { name: 'Bug' },
        };

        const issueKey = await this.jiraClient.createIssue(issueData);
        logger.info(`Created issue: ${issueKey}`);

        // Simulação de monitoramento
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (error) {
      logger.error('Error monitoring events:', error);
    }
  }

  async registerLogs() {
    try {
      const sessionId = await this.jiraClient.login();
      logger.info('Logged in as Jira user');

      // Simulação de logs
      for (let i = 0; i < 10; i++) {
        const logData = `Log ${i}`;

        await axios.post(`${this.jiraUrl}/rest/api/2/log`, {
          fields: { message: logData },
          session: { id: sessionId },
        });
        logger.info(`Logged: ${logData}`);

        // Simulação de monitoramento
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (error) {
      logger.error('Error registering logs:', error);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient);

  await javascriptAgent.monitorEvents();
  await javascriptAgent.registerLogs();
}

if (require.main === module) {
  main().catch(error => logger.error('Error in main:', error));
}