import { expect } from 'chai';
import axios from 'axios';
import { JiraClient } from './JiraClient';

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraClient: JiraClient) {
    this.jiraClient = jiraClient;
  }

  async monitorActivities(): Promise<void> {
    try {
      const activities = await this.jiraClient.getActivities();
      console.log('Actividades:');
      activities.forEach(activity => {
        console.log(`- ${activity}`);
      });
    } catch (error) {
      console.error('Erro ao monitorar atividades:', error);
    }
  }

  async registerEvent(event: string): Promise<void> {
    try {
      await this.jiraClient.registerEvent(event);
      console.log(`Evento registrado: ${event}`);
    } catch (error) {
      console.error('Erro ao registrar evento:', error);
    }
  }
}

class JiraClient {
  private apiUrl: string;

  constructor(apiUrl: string) {
    this.apiUrl = apiUrl;
  }

  async getActivities(): Promise<string[]> {
    try {
      const response = await axios.get(`${this.apiUrl}/rest/api/2/issue/activity`);
      return response.data.map(activity => activity.key);
    } catch (error) {
      throw new Error(`Erro ao obter atividades: ${error}`);
    }
  }

  async registerEvent(event: string): Promise<void> {
    try {
      await axios.post(`${this.apiUrl}/rest/api/2/issue/activity`, { event });
    } catch (error) {
      throw new Error(`Erro ao registrar evento: ${error}`);
    }
  }
}

async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net/rest/api/2');
  const agent = new TypeScriptAgent(jiraClient);

  try {
    await agent.monitorActivities();
    await agent.registerEvent('typescript-agent:activity-monitored');
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

if (require.main === module) {
  main();
}