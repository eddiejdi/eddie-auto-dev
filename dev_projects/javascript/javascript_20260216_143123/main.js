// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Função principal
async function main() {
  try {
    // Configuração do cliente de Jira
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Função para registrar eventos no Jira
    async function logEvent(issueId, eventType, eventData) {
      const issue = await jiraClient.issue.get({ id: issueId });
      const comment = await jiraClient.comment.create({
        issueId,
        body: `Event Type: ${eventType}\nEvent Data: ${eventData}`
      });

      console.log(`Comment created for issue ${issue.key}: ${comment.body}`);
    }

    // Função para monitorar atividades
    async function monitorActivity(issueId) {
      try {
        const issues = await jiraClient.issue.search({
          query: `key=${issueId}`,
          fields: ['summary', 'status']
        });

        if (issues.length > 0) {
          console.log(`Issue ${issues[0].key} is now in status ${issues[0].fields.status.name}`);
        } else {
          console.log(`Issue ${issueId} not found`);
        }
      } catch (error) {
        console.error('Error monitoring activity:', error);
      }
    }

    // Exemplo de uso das funções
    const issueId = 'ABC-123';
    logEvent(issueId, 'Task Completed', 'The task was completed successfully.');
    monitorActivity(issueId);

  } catch (error) {
    console.error('Error in main:', error);
  }
}

// Executa a função principal se o arquivo for executado como um script
if (require.main === module) {
  main();
}