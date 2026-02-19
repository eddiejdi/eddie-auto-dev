// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Função para conectar ao Jira
async function connectToJira() {
  const jiraClient = new JiraClient({
    auth: {
      username: 'your_username',
      password: 'your_password'
    },
    protocol: 'https',
    host: 'your_jira_host',
    port: 443,
    pathPrefix: '/rest/api/2'
  });

  try {
    await jiraClient.authenticate();
    console.log('Connected to Jira');
    return jiraClient;
  } catch (error) {
    console.error('Failed to connect to Jira:', error);
    throw error;
  }
}

// Função para registrar eventos em Jira
async function registerEvent(jiraClient, event) {
  try {
    const response = await jiraClient.issue.create({
      fields: {
        summary: event.summary,
        description: event.description,
        priority: { name: 'High' },
        assignee: { key: 'your_assignee_key' }
      }
    });

    console.log('Event registered:', response);
  } catch (error) {
    console.error('Failed to register event:', error);
    throw error;
  }
}

// Função principal
async function main() {
  try {
    const jiraClient = await connectToJira();
    const event = {
      summary: 'New JavaScript Activity',
      description: 'This is a new JavaScript activity tracked in Jira.'
    };

    await registerEvent(jiraClient, event);
  } catch (error) {
    console.error('Error:', error);
  }
}

// Execução do código
if (require.main === module) {
  main();
}