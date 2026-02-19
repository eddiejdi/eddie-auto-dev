// Importar bibliotecas necessárias
const axios = require('axios');
const fs = require('fs');

// Classe para representar a atividade do usuário no Jira
class Activity {
  constructor(id, title, description) {
    this.id = id;
    this.title = title;
    this.description = description;
  }
}

// Função para criar um novo item de atividade no Jira
async function createActivity(title, description) {
  const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', {
    fields: {
      summary: title,
      description: description,
      issuetype: { name: 'Task' }
    }
  });

  return new Activity(response.data.id, title, description);
}

// Função para listar todas as atividades do usuário no Jira
async function listActivities() {
  const response = await axios.get('https://your-jira-instance.atlassian.net/rest/api/2/search', {
    jql: 'assignee = currentUser()',
    fields: ['id', 'summary', 'description']
  });

  return response.data.issues.map(issue => new Activity(issue.id, issue.fields.summary, issue.fields.description));
}

// Função principal do programa
async function main() {
  try {
    // Criar uma nova atividade
    const newActivity = await createActivity('Implement JavaScript Agent', 'Tracking of user activities in the application');
    console.log(`New activity created: ${newActivity.id}`);

    // Listar todas as atividades
    const allActivities = await listActivities();
    console.log('All activities:');
    allActivities.forEach(activity => console.log(`${activity.id}: ${activity.title} - ${activity.description}`));

  } catch (error) {
    console.error('Error:', error);
  }
}

// Executar a função principal
if (require.main === module) {
  main();
}