const axios = require('axios');
const { createLogger } = require('winston');

// Configuração do logger
const logger = createLogger({
  level: 'info',
  format: {
    colorize: true,
    timestamp: true,
    prettyPrint: true,
  },
});

// Classe para monitorar eventos e enviar dados para Jira
class EventMonitor {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
    this.events = [];
  }

  // Função para adicionar um evento ao monitoramento
  addEvent(event) {
    this.events.push(event);
    logger.info(`Added event: ${event}`);
  }

  // Função para enviar dados de atividade para Jira
  sendToJira() {
    try {
      const response = axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
        fields: {
          summary: this.events.join('\n'),
          description: 'Event Monitor',
          project: { key: 'YOUR_PROJECT_KEY' },
          issuetype: { name: 'Bug' },
        },
      }, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      logger.info(`Sent events to Jira: ${response.data}`);
    } catch (error) {
      logger.error(`Error sending events to Jira: ${error.message}`);
    }
  }

  // Função principal para executar o monitoramento
  async main() {
    try {
      while (true) {
        // Simulação de evento
        const event = `Event ${new Date().toISOString()}`;
        this.addEvent(event);

        // Enviando dados para Jira após um intervalo de tempo
        await new Promise(resolve => setTimeout(resolve, 5000));
        this.sendToJira();
      }
    } catch (error) {
      logger.error(`Error in main: ${error.message}`);
    }
  }
}

// Função principal do script
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const apiKey = 'YOUR_API_KEY';

  const eventMonitor = new EventMonitor(jiraUrl, apiKey);
  await eventMonitor.main();
}

// Execução do script
if (require.main === module) {
  main().catch(error => logger.error(`Error in main: ${error.message}`));
}