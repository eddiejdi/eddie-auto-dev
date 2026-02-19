const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

// Classe para representar o JavaScript Agent
class JavaScriptAgent {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  // Função para criar uma atividade na Jira
  async createActivity(title, description, projectKey) {
    try {
      const token = await this.generateToken();
      const activityData = {
        fields: {
          summary: title,
          description: description,
          issuetype: { name: 'Task' },
          project: { key: projectKey }
        }
      };

      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, activityData, {
        headers: {
          'Authorization': `Basic ${token}`,
          'Content-Type': 'application/json'
        }
      });

      console.log(`Activity created successfully: ${response.data.key}`);
    } catch (error) {
      console.error('Error creating activity:', error);
    }
  }

  // Função para gerar um token de autenticação
  async generateToken() {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/session`, {
        username: this.username,
        password: this.password
      });

      return response.data.session.token;
    } catch (error) {
      console.error('Error generating token:', error);
      throw new Error('Failed to generate token');
    }
  }

  // Função para executar o script como um programa de linha de comando
  static async main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new JavaScriptAgent(jiraUrl, username, password);
    await agent.createActivity('Test Activity', 'This is a test activity.', 'YOUR_PROJECT_KEY');
  }
}

// Execução do script se for chamado como um programa de linha de comando
if (require.main === module) {
  JavaScriptAgent.main().catch(console.error);
}