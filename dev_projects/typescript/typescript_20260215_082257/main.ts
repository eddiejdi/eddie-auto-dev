// Importações necessárias
import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

// Função principal
async function main() {
  try {
    // Configuração do Jira Client
    const jira = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Configuração do TypeScript Agent
    const agent = new Agent(jira);

    // Função para criar uma tarefa no Jira
    async function createTask(title: string, description: string) {
      try {
        const task = await agent.createIssue({
          fields: {
            project: { key: 'YOUR_PROJECT_KEY' },
            summary: title,
            description: description,
            issuetype: { name: 'Bug' }
          }
        });

        console.log(`Task created successfully: ${task.key}`);
      } catch (error) {
        console.error('Error creating task:', error);
      }
    }

    // Função para monitorar atividades no Jira
    async function monitorActivities() {
      try {
        const issues = await agent.searchIssues({
          jql: 'project = YOUR_PROJECT_KEY AND status = Open'
        });

        for (const issue of issues) {
          console.log(`Issue ${issue.key}: ${issue.fields.summary}`);
        }
      } catch (error) {
        console.error('Error monitoring activities:', error);
      }
    }

    // Exemplo de uso das funções
    await createTask('Implement TypeScript Agent with Jira', 'This is a test task to integrate TypeScript Agent with Jira.');
    await monitorActivities();

  } catch (error) {
    console.error('Main function failed:', error);
  }
}

// Executa a função principal
if (require.main === module) {
  main();
}