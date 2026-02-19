const axios = require('axios');
const { get } = require('http');

// Classe para representar uma atividade no Jira
class Activity {
  constructor(id, title, status) {
    this.id = id;
    this.title = title;
    this.status = status;
  }

  // Método para atualizar o status da atividade
  updateStatus(newStatus) {
    this.status = newStatus;
  }
}

// Classe para representar a integração com Jira
class JiraIntegration {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  // Método para coletar atividades do Jira
  async getActivities() {
    try {
      const response = await axios.get(`${this.jiraUrl}/rest/api/2/search`, {
        auth: { username: this.username, password: this.password },
        params: {
          jql: 'project = YOUR_PROJECT_KEY AND status in (OPEN, IN_PROGRESS)',
          fields: ['id', 'summary', 'status']
        }
      });

      const activities = response.data.items.map(item => new Activity(item.id, item.fields.summary, item.fields.status));
      return activities;
    } catch (error) {
      console.error('Erro ao coletar atividades:', error);
      throw error;
    }
  }

  // Método para atualizar o status de uma atividade
  async updateActivityStatus(activityId, newStatus) {
    try {
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${activityId}`, {
        fields: { status: newStatus }
      });

      console.log(`Atividade ${activityId} atualizada para ${newStatus}`);
    } catch (error) {
      console.error('Erro ao atualizar atividade:', error);
      throw error;
    }
  }
}

// Função principal
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  // Criar instância da classe JiraIntegration
  const jiraIntegration = new JiraIntegration(jiraUrl, username, password);

  try {
    // Caso de sucesso com valores válidos
    const activities = await jiraIntegration.getActivities();
    console.log('Atividades coletadas:', activities);

    // Caso de erro (divisão por zero, valores inválidos, etc)
    const invalidStatus = 'INVALID';
    await jiraIntegration.updateActivityStatus('12345', invalidStatus);
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Executar o programa
if (require.main === module) {
  main();
}