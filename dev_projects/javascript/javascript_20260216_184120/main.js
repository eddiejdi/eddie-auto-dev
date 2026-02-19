// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

// Configuração do Jira Client
const jiraClient = new JiraClient({
  auth: {
    username: 'your_username',
    password: 'your_password'
  },
  options: {
    host: 'your_jira_host',
    port: your_jira_port,
    protocol: 'https'
  }
});

// Função para integrar JavaScript Agent com Jira
async function integrateJavaScriptAgentWithJira() {
  try {
    // Monitoramento de atividades
    const activities = await jiraClient.searchActivities({
      query: 'type=issue AND status!=closed',
      fields: ['summary', 'status']
    });

    console.log('Atividades:');
    activities.items.forEach(activity => {
      console.log(`- ${activity.fields.summary} - Status: ${activity.fields.status}`);
    });

    // Registro de eventos
    const event = await jiraClient.createEvent({
      issueKey: 'YOUR_ISSUE_KEY',
      type: 'issueCommented',
      fields: {
        comment: 'This is an example comment from JavaScript Agent.'
      }
    });

    console.log('Evento registrado:', event);
  } catch (error) {
    console.error('Erro ao integrar JavaScript Agent com Jira:', error);
  }
}

// Função main para executar o script
async function main() {
  try {
    await integrateJavaScriptAgentWithJira();
  } catch (error) {
    console.error('Ocorreu um erro na execução do script:', error);
  }
}

if (require.main === module) {
  main();
}