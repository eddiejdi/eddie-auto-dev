const axios = require('axios');
const { createLogger } = require('winston');

// Configuração do Winston para logs
const logger = createLogger({
  level: 'info',
  format: {
    json: true,
  },
});

// Função para enviar logs para Jira
async function sendLogToJira(log) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/log', log, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${Buffer.from('your-username:your-password').toString('base64')}`,
      },
    });
    logger.info(`Log enviado com sucesso: ${response.data}`);
  } catch (error) {
    logger.error(`Erro ao enviar log para Jira: ${error.message}`);
  }
}

// Função para monitorar atividades em JavaScript
async function monitorJavaScriptActivities() {
  try {
    const response = await axios.get('https://your-javascript-agent-instance.com/activities');
    const activities = response.data;

    for (const activity of activities) {
      if (activity.status === 'completed') {
        sendLogToJira({
          message: `Activity completed: ${activity.description}`,
          level: 'info',
        });
      } else {
        sendLogToJira({
          message: `Activity in progress: ${activity.description}`,
          level: 'warning',
        });
      }
    }
  } catch (error) {
    logger.error(`Erro ao monitorar atividades em JavaScript: ${error.message}`);
  }
}

// Função principal
async function main() {
  try {
    await monitorJavaScriptActivities();
  } catch (error) {
    logger.error('Ocorreu um erro no programa:', error);
  }
}

if (require.main === module) {
  main();
}