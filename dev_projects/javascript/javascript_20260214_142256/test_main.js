const axios = require('axios');
const { JiraClient } = require('@atlassian/node-jira-client');

// Função para criar uma instância do cliente Jira
function createJiraClient(apiToken, serverUrl) {
  return new JiraClient({
    auth: {
      token: apiToken,
    },
    server: serverUrl,
  });
}

// Função para registrar um evento em Jira
async function registerEvent(jiraClient, projectKey, issueId, eventType, eventData) {
  try {
    const response = await jiraClient.issue.createComment({
      fields: {
        project: { key: projectKey },
        issue: { id: issueId },
        body: {
          type: 'doc',
          version: 1,
          content: [
            {
              type: 'paragraph',
              text: `Event Type: ${eventType}\nEvent Data: ${eventData}`,
            },
          ],
        },
      },
    });
    console.log('Evento registrado com sucesso:', response);
  } catch (error) {
    console.error('Erro ao registrar evento:', error);
  }
}

// Função principal
async function main() {
  const apiKey = 'your_api_token_here';
  const serverUrl = 'https://your_jira_server_url_here';
  const projectKey = 'YOUR_PROJECT_KEY_HERE';
  const issueId = 'YOUR_ISSUE_ID_HERE';

  try {
    // Criar instância do cliente Jira
    const jiraClient = createJiraClient(apiKey, serverUrl);

    // Registrar um evento em Jira
    await registerEvent(jiraClient, projectKey, issueId, 'Task Completed', 'Task completed by user');
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Executar a função main()
if (require.main === module) {
  main();
}