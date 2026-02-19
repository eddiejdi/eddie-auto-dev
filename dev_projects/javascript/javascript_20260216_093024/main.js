// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@octokit/rest');

// Função para registrar eventos no Jira
async function registerEvent(event) {
  try {
    const client = new JiraClient({
      auth: 'your-jira-auth-token',
      url: 'https://your-jira-instance.atlassian.net'
    });

    await client.request('POST', '/rest/api/3/issue', {
      fields: {
        summary: event.summary,
        description: event.description,
        priority: { name: event.priority },
        status: { name: event.status }
      }
    });

    console.log(`Event registered successfully: ${event.summary}`);
  } catch (error) {
    console.error('Error registering event:', error);
  }
}

// Função para monitorar atividades
async function monitorActivity() {
  try {
    const client = new JiraClient({
      auth: 'your-jira-auth-token',
      url: 'https://your-jira-instance.atlassian.net'
    });

    const issues = await client.request('GET', '/rest/api/3/search', {
      jql: 'status = Open AND assignee = currentUser()',
      fields: ['summary', 'description', 'priority', 'status']
    });

    issues.items.forEach(issue => {
      console.log(`Issue ${issue.key}: ${issue.fields.summary}`);
      registerEvent({
        summary: `Activity for issue ${issue.key}`,
        description: `User ${issue.fields.assignee.displayName} is working on ${issue.fields.summary}`,
        priority: issue.fields.priority.name,
        status: issue.fields.status.name
      });
    });
  } catch (error) {
    console.error('Error monitoring activity:', error);
  }
}

// Função principal
async function main() {
  try {
    await monitorActivity();
  } catch (error) {
    console.error('Main function failed:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main();
}