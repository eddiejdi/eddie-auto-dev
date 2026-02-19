// Importações necessárias
import { JiraClient } from 'jira-client';
import { Event } from './Event';

// Definição da classe JiraAgent
class JiraAgent {
  private jiraClient: JiraClient;

  constructor(jiraHost: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      host: jiraHost,
      auth: { username, password },
    });
  }

  // Função para registrar eventos
  async registerEvent(event: Event): Promise<void> {
    try {
      await this.jiraClient.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' }, // Substitua pelo código do projeto
          summary: event.summary,
          description: event.description,
          issuetype: { name: 'Task' }, // Substitua pelo tipo de issue
        },
      });
      console.log(`Event registered successfully: ${event.summary}`);
    } catch (error) {
      console.error('Error registering event:', error);
    }
  }

  // Função para monitorar atividades
  async monitorActivity(): Promise<void> {
    try {
      const issues = await this.jiraClient.searchIssues({
        jql: 'project = YOUR_PROJECT_KEY', // Substitua pelo código do projeto
      });
      console.log('Current activities:');
      issues.forEach(issue => {
        console.log(`- ${issue.fields.summary}`);
      });
    } catch (error) {
      console.error('Error monitoring activity:', error);
    }
  }

  // Função principal para execução do script
  async main(): Promise<void> {
    const jiraHost = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new JiraAgent(jiraHost, username, password);

    // Registrar um evento
    await agent.registerEvent({
      summary: 'New feature request',
      description: 'Implement a new feature for the application.',
    });

    // Monitorar atividades
    await agent.monitorActivity();
  }
}

// Execução do script (se for CLI)
if (require.main === module) {
  JiraAgent.main().catch(error => console.error('Error running script:', error));
}