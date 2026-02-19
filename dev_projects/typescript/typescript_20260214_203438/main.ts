import { Client } from '@atlassian/issue-client';
import { Issue } from '@atlassian/issue-client';

// Configuração do cliente para Jira
const client = new Client({
  serverUrl: 'https://your-jira-server.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

async function main() {
  try {
    // Listar todos os issues
    const issues = await client.searchIssues({ jql: 'project = YOUR_PROJECT_KEY' });

    if (issues.length === 0) {
      console.log('No issues found.');
      return;
    }

    // Exibir informações sobre cada issue
    for (const issue of issues) {
      console.log(`Issue ID: ${issue.id}`);
      console.log(`Summary: ${issue.fields.summary}`);
      console.log(`Status: ${issue.fields.status.name}`);
      console.log(`Assignee: ${issue.fields.assignee ? issue.fields.assignee.displayName : 'Unassigned'}`);
    }
  } catch (error) {
    console.error('Error fetching issues:', error);
  }
}

if (require.main === module) {
  main();
}