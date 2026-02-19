// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@atlassian/node-jira-client');

// Função para conectar ao Jira
async function connectToJira() {
  const jiraClient = new JiraClient({
    username: 'your_username',
    password: 'your_password',
    options: {
      host: 'your_jira_host'
    }
  });

  try {
    await jiraClient.login();
    console.log('Connected to Jira!');
    return jiraClient;
  } catch (error) {
    console.error('Failed to connect to Jira:', error);
    throw error;
  }
}

// Função para criar uma tarefa no Jira
async function createJiraTask(jiraClient, taskTitle, description) {
  try {
    const issue = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: taskTitle,
        description: description
      }
    });

    console.log('Created Jira task:', issue.key);
    return issue;
  } catch (error) {
    console.error('Failed to create Jira task:', error);
    throw error;
  }
}

// Função para monitorar atividades no Jira
async function monitorJiraActivity(jiraClient, issueKey) {
  try {
    const issues = await jiraClient.searchIssues({
      jql: `issuekey=${issueKey}`,
      fields: ['summary', 'status']
    });

    console.log('Monitoring Jira activity for issue:', issueKey);
    return issues;
  } catch (error) {
    console.error('Failed to monitor Jira activity:', error);
    throw error;
  }
}

// Função principal
async function main() {
  try {
    // Conectar ao Jira
    const jiraClient = await connectToJira();

    // Criar uma tarefa no Jira
    const taskTitle = 'New JavaScript Activity';
    const description = 'This is a new activity tracked by JavaScript Agent.';
    const issue = await createJiraTask(jiraClient, taskTitle, description);

    // Monitorar atividades do Jira
    const issues = await monitorJiraActivity(jiraClient, issue.key);
    console.log('Monitoring results:', issues);

  } catch (error) {
    console.error('An error occurred:', error);
  }
}

// Executar a função principal se o script for executado como um módulo
if (require.main === module) {
  main();
}