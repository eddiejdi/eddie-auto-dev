import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from './TypeScriptAgent';

// Configuração do Jira Client
const jiraClient = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  auth: {
    username: 'your-username',
    password: 'your-password'
  }
});

// Classe para gerenciar o TypeScript Agent
class TypeScriptAgentManager {
  private agent: TypeScriptAgent;

  constructor() {
    this.agent = new TypeScriptAgent();
  }

  async startTracking() {
    try {
      await this.agent.startTracking(jiraClient);
      console.log('TypeScript Agent started tracking');
    } catch (error) {
      console.error('Error starting TypeScript Agent:', error);
    }
  }

  async stopTracking() {
    try {
      await this.agent.stopTracking();
      console.log('TypeScript Agent stopped tracking');
    } catch (error) {
      console.error('Error stopping TypeScript Agent:', error);
    }
  }
}

// Execução do script
(async () => {
  const manager = new TypeScriptAgentManager();
  await manager.startTracking();
  // Aguarde algum tempo para simular atividades no Jira
  await new Promise(resolve => setTimeout(resolve, 5000));
  await manager.stopTracking();
})();