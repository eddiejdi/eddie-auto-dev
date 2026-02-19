const axios = require('axios');
const { createLogger, format } = require('winston');

// Configuração do logger
const logger = createLogger({
  level: 'info',
  format: format.json(),
});

// Função para realizar o login no Jira
async function testLoginJira() {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/session', {
      username: 'valid-username',
      password: 'valid-password',
    });
    logger.info(`Login realizado com sucesso: ${response.data.token}`);
    return response.data.token;
  } catch (error) {
    logger.error(`Erro ao realizar login no Jira: ${error.message}`);
    throw error;
  }
}

// Função para registrar um evento em Jira
async function testRegisterEvent() {
  try {
    const token = await testLoginJira();
    const event = {
      summary: 'Novo evento registrado',
      description: 'Este é um novo evento registrado para testar a integração.',
    };
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/issue', {
      fields: {
        summary: event.summary,
        description: event.description,
        priority: { name: 'High' },
        assignee: { key: 'assignee-key' }, // Substitua com o ID do usuário
      },
    });
    logger.info(`Evento registrado com sucesso: ${response.data.key}`);
  } catch (error) {
    logger.error(`Erro ao registrar evento no Jira: ${error.message}`);
    throw error;
  }
}

// Função principal para executar a integração
async function main() {
  try {
    const token = await testLoginJira();
    const event = {
      summary: 'Novo evento registrado',
      description: 'Este é um novo evento registrado para testar a integração.',
    };
    await testRegisterEvent(token, event);

    logger.info('Integração com Jira realizada com sucesso!');
  } catch (error) {
    logger.error('Erro ao realizar a integração com Jira:', error);
  }
}

// Execução da função principal
if (require.main === module) {
  main();
}