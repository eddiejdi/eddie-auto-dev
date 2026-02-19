// Importar o JavaScript Agent
const jsAgent = require('js-agent');

// Configurar a conexão com Jira
const jiraConfig = {
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
};

// Inicializar o JavaScript Agent
jsAgent.init(jiraConfig);

// Função para criar um ticket no Jira
async function createTicket(title, description) {
  try {
    const response = await jsAgent.createIssue({
      fields: {
        project: { key: 'YOUR-PROJECT' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    });

    console.log('Ticket created:', response);
  } catch (error) {
    console.error('Error creating ticket:', error);
  }
}

// Função para atualizar um ticket no Jira
async function updateTicket(ticketId, title, description) {
  try {
    const response = await jsAgent.updateIssue({
      issueKey: ticketId,
      fields: {
        summary: title,
        description: description
      }
    });

    console.log('Ticket updated:', response);
  } catch (error) {
    console.error('Error updating ticket:', error);
  }
}

// Função para fechar um ticket no Jira
async function closeTicket(ticketId) {
  try {
    const response = await jsAgent.updateIssue({
      issueKey: ticketId,
      fields: {
        status: { name: 'Closed' }
      }
    });

    console.log('Ticket closed:', response);
  } catch (error) {
    console.error('Error closing ticket:', error);
  }
}

// Função para listar todos os tickets do usuário no Jira
async function listTickets() {
  try {
    const response = await jsAgent.searchIssues({
      jql: 'assignee = currentUser()'
    });

    console.log('Tickets:', response.issues);
  } catch (error) {
    console.error('Error listing tickets:', error);
  }
}

// Função principal para executar as funcionalidades
async function main() {
  try {
    await createTicket('Bug in login page', 'The login page is not working properly.');
    await updateTicket('12345', 'Fixed the login page issue.', 'The login page now works correctly.');
    await closeTicket('12345');
    await listTickets();
  } catch (error) {
    console.error('Error in main:', error);
  }
}

// Executar a função principal
if (require.main === module) {
  main();
}