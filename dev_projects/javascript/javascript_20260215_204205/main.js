// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Configuração do cliente de Jira
const jiraClient = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

// Função para criar uma tarefa no Jira
async function createJiraIssue(title, description) {
  try {
    const issue = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description
      }
    });

    console.log('Tarefa criada com sucesso:', issue.key);
  } catch (error) {
    console.error('Erro ao criar tarefa no Jira:', error);
  }
}

// Função para monitorar atividades em JavaScript
async function monitorJavaScriptActivity() {
  try {
    const response = await axios.get('https://your-javascript-agent-url');
    const activities = response.data;

    for (const activity of activities) {
      console.log(`Atividade: ${activity.type} - ${activity.message}`);
      await createJiraIssue(activity.title, activity.description);
    }
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
}

// Função principal
async function main() {
  try {
    await monitorJavaScriptActivity();
  } catch (error) {
    console.error('Erro no programa principal:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}