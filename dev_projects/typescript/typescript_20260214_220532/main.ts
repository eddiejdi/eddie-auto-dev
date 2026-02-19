import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

// Configuração do Jira Client
const jira = new JiraClient({
  url: 'https://your-jira-url.com',
  username: 'your-username',
  password: 'your-password'
});

// Função para integrar TypeScript Agent com Jira
async function integrateTypeScriptAgentWithJira() {
  try {
    // Cria um agente TypeScript
    const agent = new Agent();

    // Adiciona uma atividade ao agente
    await agent.addActivity('Starting TypeScript Agent');

    // Realiza a integração com Jira usando o agente TypeScript
    await jira.addIssue({
      project: 'YOUR_PROJECT_KEY',
      summary: 'Integrating TypeScript Agent with Jira',
      description: 'This is an example of integrating TypeScript Agent with Jira using the Jira Client.'
    });

    // Adiciona outra atividade ao agente
    await agent.addActivity('Integration completed successfully');

    console.log('TypeScript Agent integrated with Jira successfully.');
  } catch (error) {
    console.error('Error integrating TypeScript Agent with Jira:', error);
  }
}

// Função principal do programa
async function main() {
  try {
    // Inicia a integração com TypeScript Agent e Jira
    await integrateTypeScriptAgentWithJira();
  } finally {
    // Finaliza o agente TypeScript
    await agent.close();
  }
}

if (require.main === module) {
  main().catch(error => console.error('Error in main:', error));
}