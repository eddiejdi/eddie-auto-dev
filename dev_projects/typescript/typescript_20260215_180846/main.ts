// Importações necessárias
import { JiraClient } from 'jira-client';
import { ScrumBoard } from './ScrumBoard';

// Função principal do programa
async function main() {
  try {
    // Configuração do cliente Jira
    const jira = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Cria uma instância de ScrumBoard
    const scrumBoard = new ScrumBoard(jira);

    // Monitoramento de atividades em tempo real
    scrumBoard.startMonitoring();

    // Gerenciamento de tarefas com detalhes específicos
    scrumBoard.manageTasks();
  } catch (error) {
    console.error('Erro ao executar o programa:', error);
  }
}

// Executa a função principal se o script for chamado diretamente
if (require.main === module) {
  main();
}