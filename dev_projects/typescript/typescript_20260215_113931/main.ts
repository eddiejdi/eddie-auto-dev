// Importações necessárias
import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from './TypeScriptAgent';

// Função principal do programa
async function main() {
  try {
    // Configuração da conexão com Jira
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Cria uma instância do TypeScriptAgent
    const agent = new TypeScriptAgent(jiraClient);

    // Inicia o monitoramento de atividades
    await agent.startMonitoring();
  } catch (error) {
    console.error('Error:', error);
  }
}

// Executa a função main() se o script for executado diretamente
if (require.main === module) {
  main();
}