const axios = require('axios');
const { createLogger } = require('winston');

// Configuração do logger
const logger = createLogger({
  level: 'info',
  format: 'json'
});

// Função para enviar logs para Jira
async function sendLogToJira(log) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/issue', {
      fields: {
        summary: `JavaScript Log: ${log.message}`,
        description: log.stackTrace,
        status: 'Open'
      }
    });
    logger.info(`Log enviado com sucesso. ID do issue: ${response.data.id}`);
  } catch (error) {
    logger.error('Erro ao enviar log para Jira:', error);
  }
}

// Função para monitorar atividades
async function monitorActivities() {
  try {
    const response = await axios.get('https://your-jira-instance.atlassian.net/rest/api/3/issue');
    response.data.forEach(issue => {
      logger.info(`Issue: ${issue.key}, Status: ${issue.fields.status.name}`);
      if (issue.fields.status.name === 'Closed') {
        sendLogToJira({
          message: `Issue ${issue.key} foi fechado`,
          stackTrace: issue.fields.description
        });
      }
    });
  } catch (error) {
    logger.error('Erro ao monitorar atividades:', error);
  }
}

// Função principal
async function main() {
  try {
    await monitorActivities();
  } catch (error) {
    logger.error('Erro na execução do programa:', error);
  }
}

// Executa a função principal se o arquivo for executado diretamente
if (require.main === module) {
  main();
}