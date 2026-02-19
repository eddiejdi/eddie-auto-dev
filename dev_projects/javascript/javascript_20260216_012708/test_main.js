const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Função principal do programa
async function main() {
  try {
    // Configuração do cliente de Jira
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Função para criar uma tarefa no Jira
    async function createIssue(title, description) {
      const issueData = {
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' }
        }
      };

      const response = await jiraClient.createIssue(issueData);
      console.log('Tarefa criada:', response.data.key);
    }

    // Função para atualizar uma tarefa no Jira
    async function updateIssue(issueKey, title, description) {
      const issueData = {
        fields: {
          summary: title,
          description: description
        }
      };

      const response = await jiraClient.updateIssue(issueKey, issueData);
      console.log('Tarefa atualizada:', response.data.key);
    }

    // Função para deletar uma tarefa no Jira
    async function deleteIssue(issueKey) {
      const response = await jiraClient.deleteIssue(issueKey);
      console.log('Tarefa deletada:', response.data.key);
    }

    // Exemplo de uso das funções
    await createIssue('Teste de Tarefa', 'Descrição da tarefa para teste');
    await updateIssue('TEST-123', 'Atualização da tarefa', 'Nova descrição da tarefa');
    await deleteIssue('TEST-123');

  } catch (error) {
    console.error('Ocorreu um erro:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}