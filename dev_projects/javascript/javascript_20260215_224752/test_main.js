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
  pathPrefix: '/rest/api/2.0/'
});

// Função para criar um novo issue
async function createIssue(title, description) {
  try {
    const response = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Task' }
      }
    });

    console.log('Issue created:', response.data);
  } catch (error) {
    console.error('Error creating issue:', error);
  }
}

// Função para atualizar um issue
async function updateIssue(issueId, title, description) {
  try {
    const response = await jiraClient.updateIssue({
      fields: {
        summary: title,
        description: description
      },
      id: issueId
    });

    console.log('Issue updated:', response.data);
  } catch (error) {
    console.error('Error updating issue:', error);
  }
}

// Função para listar issues
async function listIssues() {
  try {
    const response = await jiraClient.searchJql({
      jql: 'project = YOUR_PROJECT_KEY',
      fields: ['summary', 'description']
    });

    console.log('Issues listed:', response.data.issues);
  } catch (error) {
    console.error('Error listing issues:', error);
  }
}

// Função para exibir logs em tempo real
async function logRealTime() {
  try {
    const stream = await jiraClient.streamLogs({
      project: { key: 'YOUR_PROJECT_KEY' },
      fields: ['summary', 'description']
    });

    for await (const event of stream) {
      console.log('Log:', event);
    }
  } catch (error) {
    console.error('Error logging real-time:', error);
  }
}

// Função principal
async function main() {
  try {
    // Criar um novo issue com sucesso
    await createIssue('Test Issue', 'This is a test issue created using JavaScript Agent with Jira.');

    // Atualizar um issue com sucesso
    await updateIssue('YOUR_ISSUE_ID', 'Updated summary', 'Updated description');

    // Listar issues com sucesso
    await listIssues();

    // Exibir logs em tempo real com sucesso
    await logRealTime();
  } catch (error) {
    console.error('Error in main:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main().catch(console.error);
}