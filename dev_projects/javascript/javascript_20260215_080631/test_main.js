const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Configuração do Jira Client
const jiraClient = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

// Função para criar uma tarefa no Jira
async function createTask(title, description) {
  try {
    const task = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        priority: { name: 'High' }
      }
    });

    console.log(`Tarefa criada com ID: ${task.id}`);
  } catch (error) {
    console.error('Erro ao criar tarefa:', error);
  }
}

// Função para monitorar atividades no Jira
async function monitorTasks() {
  try {
    const issues = await jiraClient.searchIssues({
      jql: 'project = YOUR_PROJECT_KEY AND status = In Progress',
      fields: ['summary', 'status']
    });

    console.log('Tarefas em progresso:');
    issues.forEach(issue => {
      console.log(`ID: ${issue.id}, Summary: ${issue.fields.summary}, Status: ${issue.fields.status.name}`);
    });
  } catch (error) {
    console.error('Erro ao monitorar tarefas:', error);
  }
}

// Função principal
async function main() {
  try {
    // Criar uma nova tarefa com valores válidos
    await createTask('Novo Tarefa', 'Descrição da nova tarefa');

    // Monitorar atividades com valores válidos
    await monitorTasks();
  } catch (error) {
    console.error('Erro no sistema:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}