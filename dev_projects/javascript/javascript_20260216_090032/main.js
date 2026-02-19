// Importa o JavaScript Agent SDK
const agent = require('js-agent-sdk');

// Configura a conexão com Jira
agent.config({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

// Função para iniciar o monitoramento de atividades
function startMonitoring() {
  // Adiciona um listener para eventos de atividade
  agent.on('activity', (event) => {
    try {
      // Loga a atividade no console
      console.log(`Activity: ${event.name}`);
      
      // Envia a atividade para Jira usando o JavaScript Agent SDK
      agent.send(event);
    } catch (error) {
      // Trata erros de envio
      console.error('Error sending activity to Jira:', error);
    }
  });
}

// Função principal do script
function main() {
  try {
    // Inicia o monitoramento de atividades
    startMonitoring();
    
    // Pausa a execução para esperar eventos (opcional)
    process.stdin.on('data', () => {});
  } catch (error) {
    // Trata erros principais do script
    console.error('Error starting monitoring:', error);
  }
}

// Executa o script
if (require.main === module) {
  main();
}