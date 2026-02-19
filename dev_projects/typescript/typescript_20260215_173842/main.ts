// Importações necessárias
import { JiraClient } from 'jira-client';
import { Agent } from './agent';

// Classe para representar a integração TypeScript Agent com Jira
class TypeScriptAgentJira {
  private jiraClient: JiraClient;
  private agent: Agent;

  constructor(jiraClient: JiraClient, agent: Agent) {
    this.jiraClient = jiraClient;
    this.agent = agent;
  }

  async startTracking() {
    try {
      // Iniciar o tracking do TypeScript Agent no Jira
      await this.agent.startTracking(this.jiraClient);
      console.log('Tracking started successfully');
    } catch (error) {
      console.error('Error starting tracking:', error);
    }
  }

  async stopTracking() {
    try {
      // Parar o tracking do TypeScript Agent no Jira
      await this.agent.stopTracking(this.jiraClient);
      console.log('Tracking stopped successfully');
    } catch (error) {
      console.error('Error stopping tracking:', error);
    }
  }
}

// Função principal para execução do script
async function main() {
  // Configurações do Jira Client
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net',
    username: 'your-username',
    password: 'your-password'
  });

  // Criação de um objeto Agent
  const agent = new Agent();

  // Instância da classe TypeScriptAgentJira
  const tsAgentJira = new TypeScriptAgentJira(jiraClient, agent);

  try {
    await tsAgentJira.startTracking();
    await tsAgentJira.stopTracking();
  } catch (error) {
    console.error('Main function failed:', error);
  }
}

// Execução do script
if (require.main === module) {
  main().catch(error => console.error('Error in main:', error));
}