const axios = require('axios');
const { createLogger, format } = require('winston');

// Configuração do logger
const logger = createLogger({
  level: 'info',
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'app.log' })
  ],
  format: format.combine(
    format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    format.json()
  )
});

// Função para enviar log para Jira
async function sendLogToJira(log) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: `JavaScript Log - ${log.message}`,
        description: log.stackTrace,
        priority: { name: 'High' }
      }
    });
    logger.info(`Log sent to Jira with ID: ${response.data.id}`);
  } catch (error) {
    logger.error('Failed to send log to Jira', error);
  }
}

// Função para monitorar atividades
async function monitorActivities() {
  try {
    const response = await axios.get('https://your-jira-instance.atlassian.net/rest/api/2/search?jql=project=YOUR_PROJECT_KEY');
    logger.info(`Found ${response.data.total} issues in Jira`);
    // Aqui você pode adicionar lógica para monitorar atividades específicas
  } catch (error) {
    logger.error('Failed to monitor activities', error);
  }
}

// Função principal
async function main() {
  try {
    await sendLogToJira({ message: 'Test log', stackTrace: 'Error occurred' });
    await monitorActivities();
  } catch (error) {
    logger.error('Main function failed', error);
  }
}

if (require.main === module) {
  main();
}