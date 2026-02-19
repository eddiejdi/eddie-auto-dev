// Importações necessárias
const axios = require('axios');
const { exec } = require('child_process');

class JavaScriptAgent {
  constructor() {
    this.url = 'http://localhost:3000'; // URL do JavaScript Agent
  }

  async startMonitoring() {
    try {
      const response = await axios.get(this.url);
      console.log(response.data);
    } catch (error) {
      console.error('Erro ao iniciar monitoramento:', error);
    }
  }

  async stopMonitoring() {
    try {
      exec('pkill -f javascript-agent', (error, stdout, stderr) => {
        if (error) {
          console.error('Erro ao parar monitoramento:', error);
        } else {
          console.log('Monitoramento parado');
        }
      });
    } catch (error) {
      console.error('Erro ao parar monitoramento:', error);
    }
  }
}

async function main() {
  const agent = new JavaScriptAgent();
  await agent.startMonitoring();
  // Aguarde um tempo para simular atividades
  await new Promise(resolve => setTimeout(resolve, 5000));
  await agent.stopMonitoring();
}

if (require.main === module) {
  main().catch(error => console.error('Erro:', error));
}