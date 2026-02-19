const axios = require('axios');
const express = require('express');

// Configuração do Express
const app = express();
app.use(express.json());

// Definição da API para interação com Jira
const jiraApi = {
  url: 'https://your-jira-instance.atlassian.net/rest/api/3',
  auth: { username: 'your-username', password: 'your-password' }
};

// Função para fazer requisições à API do Jira
async function fetchJiraData(url, method, data) {
  try {
    const response = await axios({
      url,
      method,
      headers: {
        'Authorization': `Basic ${Buffer.from(`${jiraApi.auth.username}:${jiraApi.auth.password}`).toString('base64')}`
      },
      data
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching Jira data:`, error);
    throw error;
  }
}

// Função para registrar eventos no Jira
async function logEvent(issueKey, eventDescription) {
  try {
    const issue = await fetchJiraData(`${jiraApi.url}/issue/${issueKey}`, 'GET');
    const update = {
      fields: {
        comments: [
          {
            author: { name: 'Your Name' },
            body: eventDescription
          }
        ]
      }
    };
    await fetchJiraData(`${jiraApi.url}/issue/${issueKey}/comment`, 'POST', update);
  } catch (error) {
    console.error(`Error logging event to Jira:`, error);
  }
}

// Função principal do programa
async function main() {
  try {
    // Caso de sucesso com valores válidos
    await logEvent('JIRA-123', 'This is a test event from the JavaScript Agent');

    // Caso de erro (divisão por zero)
    await logEvent('JIRA-456', '0/0');

    // Caso de erro (valores inválidos)
    await logEvent('JIRA-789', 'abc');

    // Edge case (valores limite, strings vazias, None, etc)
    await logEvent('', 'This is a test event from the JavaScript Agent');
  } catch (error) {
    console.error('Error in main:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}