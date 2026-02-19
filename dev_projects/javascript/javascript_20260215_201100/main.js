// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Configuração do Jira Client
const jiraClient = new JiraClient({
  auth: {
    username: 'your_username',
    password: 'your_password'
  },
  protocol: 'https',
  host: 'your_jira_host',
  port: 443,
  pathPrefix: '/rest/api/2.0'
});

// Função para registrar atividades no Jira
async function registerActivity(activity) {
  try {
    const response = await jiraClient.request({
      method: 'POST',
      url: `/issue/${activity.issueKey}/comment`,
      body: {
        body: activity.description,
        visibility: {
          type: 'role',
          value: 'Administrators'
        }
      }
    });

    console.log('Atividade registrada com sucesso:', response.data);
  } catch (error) {
    console.error('Erro ao registrar atividade:', error);
  }
}

// Função principal
async function main() {
  try {
    // Simulação de um evento em JavaScript
    const event = {
      issueKey: 'JIRA-123',
      description: 'O usuário clicou no botão "Salvar" na página do formulário.'
    };

    // Registrar a atividade no Jira
    await registerActivity(event);

  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Execução da função main
if (require.main === module) {
  main();
}