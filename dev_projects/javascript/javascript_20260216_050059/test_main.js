const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Função para conectar ao Jira (Teste 1)
test('connectToJira should return a JiraClient instance', async () => {
  const jiraClient = await connectToJira();
  expect(jiraClient).toBeInstanceOf(JiraClient);
});

// Função para criar uma tarefa no Jira (Teste 2)
test('createTask should create a task in Jira', async () => {
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net',
    username: 'your-username',
    password: 'your-password'
  });

  try {
    await connectToJira();
    const projectKey = 'YOUR_PROJECT_KEY'; // Substitua pelo código da sua projeto
    const issueData = {
      fields: {
        project: { key: projectKey },
        summary: 'Monitoramento de JavaScript',
        description: 'Monitora eventos em JavaScript',
        issuetype: { name: 'Task' }
      }
    };

    await jiraClient.createIssue(issueData);
    console.log('Tarefa criada com sucesso!');
  } catch (error) {
    console.error('Erro ao criar tarefa:', error);
    throw error;
  }
});

// Função para monitorar eventos em JavaScript (Teste 3)
test('monitorJavaScriptEvents should monitor events in JavaScript', async () => {
  try {
    const events = [
      'console.log',
      'alert',
      'document.getElementById'
    ];

    for (const event of events) {
      console.log(`Monitorando evento: ${event}`);

      // Simulação de evento
      setTimeout(() => {
        eval(event);
      }, 1000);
    }
  } catch (error) {
    console.error('Erro ao monitorar eventos:', error);
    throw error;
  }
});