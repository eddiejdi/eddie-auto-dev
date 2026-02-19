const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

// Configuração da API do Jira
const jiraUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
const jiraToken = 'your-jira-token';

// Função para criar um ticket no Jira
async function createTicket(title, description) {
  const payload = {
    fields: {
      project: { key: 'YOUR_PROJECT_KEY' },
      summary: title,
      description: description,
      issuetype: { name: 'Task' }
    }
  };

  try {
    const response = await axios.post(`${jiraUrl}/issue`, payload, {
      headers: {
        Authorization: `Basic ${Buffer.from(`${jiraToken}:${jiraToken}`).toString('base64')}`
      }
    });

    console.log(`Ticket criado com ID: ${response.data.key}`);
  } catch (error) {
    console.error('Erro ao criar ticket:', error);
  }
}

// Função para monitorar atividades do usuário
async function monitorUserActivity(userId) {
  try {
    const response = await axios.get(`${jiraUrl}/user/${userId}`, {
      headers: {
        Authorization: `Basic ${Buffer.from(`${jiraToken}:${jiraToken}`).toString('base64')}`
      }
    });

    console.log(`Atividades do usuário ${userId}:`);
    console.log(response.data);
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
}

// Função para gerar relatórios
async function generateReport() {
  try {
    const response = await axios.get(`${jiraUrl}/report`, {
      headers: {
        Authorization: `Basic ${Buffer.from(`${jiraToken}:${jiraToken}`).toString('base64')}`
      }
    });

    console.log(`Relatório gerado:`);
    console.log(response.data);
  } catch (error) {
    console.error('Erro ao gerar relatório:', error);
  }
}

// Função principal
async function main() {
  try {
    // Criar um ticket com valores válidos
    await createTicket('Teste de Ticket', 'Descrição do teste');

    // Monitorar atividades do usuário com valores válidos
    await monitorUserActivity('USER_ID');

    // Gerar relatório com valores válidos
    await generateReport();
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Execução da função main() se o arquivo for executado como um script
if (require.main === module) {
  main();
}