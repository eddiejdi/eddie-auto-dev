const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

// Função principal do programa
async function main() {
  try {
    // Configuração da API Jira
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      options: {
        host: 'your_jira_host',
        port: 8080,
        protocol: 'http'
      }
    });

    // Função para criar uma tarefa
    async function createTask(title, description) {
      const issue = await jiraClient.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' }
        }
      });

      console.log(`Tarefa criada com ID: ${issue.id}`);
    }

    // Função para atualizar uma tarefa
    async function updateTask(taskId, title, description) {
      const issue = await jiraClient.updateIssue({
        fields: {
          summary: title,
          description: description
        },
        issueKey: taskId
      });

      console.log(`Tarefa atualizada com ID: ${issue.id}`);
    }

    // Função para obter uma tarefa por ID
    async function getTask(taskId) {
      const issue = await jiraClient.getIssue({
        issueKey: taskId
      });

      console.log(`Tarefa obtida com ID: ${issue.id}`);
    }

    // Exemplos de uso das funções
    await createTask('Novo Tarefa', 'Descrição da nova tarefa');
    await updateTask('NEW-TASK-123', 'Nova descrição da tarefa', 'Nova descrição atualizada');
    await getTask('NEW-TASK-123');

  } catch (error) {
    console.error('Erro:', error);
  }
}

// Executa a função principal
if (require.main === module) {
  main();
}