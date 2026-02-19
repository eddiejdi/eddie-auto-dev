// Importações necessárias
const axios = require('axios');
const fs = require('fs');

// Função para enviar dados para Jira
async function sendToJira(data) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/issue', data, {
      headers: {
        'Authorization': 'Basic your-auth-token',
        'Content-Type': 'application/json'
      }
    });
    console.log('Dados enviados para Jira com sucesso:', response.data);
  } catch (error) {
    console.error('Erro ao enviar dados para Jira:', error);
  }
}

// Função para monitorar atividades
async function monitorActivities() {
  try {
    const response = await axios.get('https://your-jira-instance.atlassian.net/rest/api/3/search', {
      params: {
        jql: 'status = Open',
        fields: ['summary', 'assignee']
      }
    });
    console.log('Atividades monitoradas:', response.data);
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
}

// Função para gerenciar tarefas
async function manageTasks() {
  try {
    const response = await axios.get('https://your-jira-instance.atlassian.net/rest/api/3/search', {
      params: {
        jql: 'status = In Progress',
        fields: ['summary', 'assignee']
      }
    });
    console.log('Tarefas gerenciadas:', response.data);
  } catch (error) {
    console.error('Erro ao gerenciar tarefas:', error);
  }
}

// Função principal
async function main() {
  try {
    // Monitorar atividades
    await monitorActivities();

    // Gerenciar tarefas
    await manageTasks();
  } catch (error) {
    console.error('Erro no sistema:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}