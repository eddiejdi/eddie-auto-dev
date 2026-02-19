import { JiraClient } from 'jira-client';
import { Event } from './Event';

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  registerEvent(event: Event): void {
    try {
      const issue = this.jiraClient.createIssue({
        fields: {
          summary: event.summary,
          description: event.description,
          issuetype: { name: 'Bug' }
        }
      });

      console.log(`Event registered: ${issue.key}`);
    } catch (error) {
      console.error('Error registering event:', error);
    }
  }

  analyzeData(): void {
    try {
      // Implemente aqui a lógica para analisar dados de atividades
      console.log('Data analysis in progress...');
    } catch (error) {
      console.error('Error analyzing data:', error);
    }
  }
}

class Event {
  constructor(public summary: string, public description: string) {}
}

// Exemplo de uso
const jiraUrl = 'https://your-jira-instance.atlassian.net';
const username = 'your-username';
const password = 'your-password';

const agent = new TypeScriptAgent(jiraUrl, username, password);

const event = new Event('TypeScript Agent Integration', 'This is a test event for the TypeScript Agent integration in Jira.');

agent.registerEvent(event);
agent.analyzeData();