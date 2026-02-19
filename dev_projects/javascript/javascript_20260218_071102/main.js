// Importar bibliotecas necessárias
const axios = require('axios');
const fs = require('fs');

// Função para enviar logs para Jira
async function sendLogToJira(log) {
  try {
    // Configurar o cabeçalho do request
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Basic ${process.env.JIRA_TOKEN}`
    };

    // Criar o corpo do request com os dados do log
    const body = JSON.stringify({
      fields: {
        project: { key: process.env.JIRA_PROJECT },
        summary: log.summary,
        description: log.description,
        issuetype: { name: 'Task' }
      }
    });

    // Enviar o log para Jira
    await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', body, headers);

    console.log(`Log enviado para Jira com sucesso.`);
  } catch (error) {
    console.error(`Erro ao enviar log para Jira: ${error.message}`);
  }
}

// Função principal
async function main() {
  try {
    // Ler o arquivo de logs
    const logs = fs.readFileSync('logs.txt', 'utf8');

    // Converter o texto do arquivo em um array de logs
    const logArray = logs.split('\n').map(log => JSON.parse(log));

    // Enviar cada log para Jira
    for (const log of logArray) {
      await sendLogToJira(log);
    }

    console.log('Todos os logs foram enviados para Jira com sucesso.');
  } catch (error) {
    console.error(`Erro ao ler ou enviar logs: ${error.message}`);
  }
}

// Verificar se o script foi executado diretamente
if (require.main === module) {
  main();
}