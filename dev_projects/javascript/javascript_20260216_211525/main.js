// Importações necessárias
const axios = require('axios');
const { promisify } = require('util');

// Função para enviar dados ao Jira via API
async function sendToJira(data) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', data);
    console.log('Dados enviados com sucesso:', response.data);
  } catch (error) {
    console.error('Erro ao enviar dados para Jira:', error);
  }
}

// Função para iniciar o script
async function main() {
  try {
    // Dados do issue a ser criado ou atualizado
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: 'Teste de integração JavaScript Agent com Jira',
        description: 'Descrição detalhada da atividade',
        issuetype: { name: 'Task' }
      }
    };

    // Enviar dados ao Jira
    await sendToJira(issueData);

    console.log('Script executado com sucesso');
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Verifica se o script foi chamado diretamente
if (require.main === module) {
  main();
}