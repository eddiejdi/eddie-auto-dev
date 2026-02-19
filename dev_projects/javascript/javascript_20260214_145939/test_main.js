const axios = require('axios');
const { exec } = require('child_process');

// Função para enviar dados ao Jira usando o JavaScript Agent
async function sendToJira(eventData) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', eventData, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Basic your-api-token'
      }
    });
    console.log(`Issue created successfully: ${response.data.key}`);
  } catch (error) {
    console.error('Error sending to Jira:', error);
  }
}

// Função para monitorar eventos e enviar dados ao Jira
function monitorEvents() {
  try {
    // Simulação de evento (por exemplo, um click no botão)
    const eventData = {
      projectKey: 'YOUR_PROJECT_KEY',
      issueType: 'BUG',
      summary: 'Click event detected',
      description: 'User clicked a button on the page'
    };

    sendToJira(eventData);
  } catch (error) {
    console.error('Error monitoring events:', error);
  }
}

// Função principal
async function main() {
  try {
    // Iniciar monitoramento de eventos
    monitorEvents();

    // Simulação de loop para manter o programa rodando
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      monitorEvents();
    }
  } catch (error) {
    console.error('Error in main:', error);
  }
}

// Execução do programa
if (require.main === module) {
  main().catch(error => {
    console.error('Error starting the program:', error);
  });
}