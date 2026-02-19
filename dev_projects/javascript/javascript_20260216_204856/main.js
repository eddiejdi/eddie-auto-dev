// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Função principal do programa
async function main() {
  try {
    // Configuração da conexão com o Jira
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Função para monitorar atividades em JavaScript
    async function monitorJavaScriptActivities() {
      try {
        // Faz uma solicitação ao servidor de atividades em JavaScript
        const response = await axios.get('https://your-javascript-activity-srv.com/activities');

        // Processa as atividades recebidas do servidor
        for (const activity of response.data) {
          console.log(`Activity: ${activity}`);
          await createJiraIssue(jiraClient, activity);
        }
      } catch (error) {
        console.error('Error monitoring JavaScript activities:', error);
      }
    }

    // Função para criar um issue no Jira
    async function createJiraIssue(jiraClient, activity) {
      try {
        const issue = {
          fields: {
            project: { key: 'YOUR-JIRA-PROJECT' },
            summary: `JavaScript Activity: ${activity}`,
            description: `Details of the JavaScript activity: ${activity}`
          }
        };

        await jiraClient.createIssue(issue);
        console.log(`Issue created in Jira: ${issue.key}`);
      } catch (error) {
        console.error('Error creating issue in Jira:', error);
      }
    }

    // Executa a monitoração das atividades em JavaScript
    await monitorJavaScriptActivities();
  } catch (error) {
    console.error('Main function failed:', error);
  }
}

// Verifica se o script é executado como um módulo
if (require.main === module) {
  main();
}