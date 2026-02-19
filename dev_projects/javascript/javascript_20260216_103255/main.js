const axios = require('axios');
const { JiraClient } = require('@atlassian/node-jira-client');

// Configuração do Jira Client
const jiraClient = new JiraClient({
  auth: {
    username: 'your_username',
    password: 'your_password'
  },
  host: 'your_jira_host'
});

// Função para criar uma tarefa no Jira
async function createTask(title, description) {
  try {
    const task = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description
      }
    });

    console.log(`Tarefa criada com ID: ${task.id}`);
  } catch (error) {
    console.error('Erro ao criar tarefa:', error);
  }
}

// Função para monitorar atividades em JavaScript
async function monitorActivity() {
  try {
    const response = await axios.get('https://your_javascript_agent_url');

    if (response.status === 200) {
      const activities = response.data;

      for (const activity of activities) {
        console.log(`Atividade: ${activity}`);
        await createTask(activity, 'Nova atividade monitorada');
      }
    } else {
      console.error('Erro ao obter atividades:', response.status);
    }
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
}

// Função principal
async function main() {
  try {
    await monitorActivity();
  } catch (error) {
    console.error('Erro no programa principal:', error);
  }
}

if (require.main === module) {
  main();
}