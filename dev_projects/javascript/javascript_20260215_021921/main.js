// Importa os módulos necessários
const axios = require('axios');
const { JiraClient } = require('@jira/client');

/**
 * Classe para representar uma tarefa no sistema de Trello
 */
class Task {
  constructor(id, title) {
    this.id = id;
    this.title = title;
  }
}

/**
 * Classe para representar a configuração do cliente Jira
 */
class JiraConfig {
  constructor(url, username, password) {
    this.url = url;
    this.username = username;
    this.password = password;
  }
}

/**
 * Classe para representar o cliente Jira
 */
class JiraClientImpl extends JiraClient {
  constructor(config) {
    super({
      auth: { username: config.username, password: config.password },
      headers: { 'Content-Type': 'application/json' },
      baseApiUrl: config.url,
    });
  }

  async getTasks() {
    try {
      const response = await this.get('/rest/api/2/search', {
        fields: ['id', 'summary'],
        jql: 'project = TRELLO',
      });
      return response.data.items.map(item => new Task(item.id, item.fields.summary));
    } catch (error) {
      console.error('Error fetching tasks:', error);
      throw error;
    }
  }

  async createTask(title) {
    try {
      const response = await this.post('/rest/api/2/issue', {
        fields: {
          project: { key: 'TRELLO' },
          summary: title,
          issuetype: { name: 'Bug' },
        },
      });
      return new Task(response.data.id, response.data.fields.summary);
    } catch (error) {
      console.error('Error creating task:', error);
      throw error;
    }
  }

  async updateTask(taskId, title) {
    try {
      const response = await this.put(`/rest/api/2/issue/${taskId}`, {
        fields: {
          summary: title,
        },
      });
      return new Task(response.data.id, response.data.fields.summary);
    } catch (error) {
      console.error('Error updating task:', error);
      throw error;
    }
  }

  async deleteTask(taskId) {
    try {
      await this.delete(`/rest/api/2/issue/${taskId}`);
    } catch (error) {
      console.error('Error deleting task:', error);
      throw error;
    }
  }
}

/**
 * Função principal para executar o script
 */
async function main() {
  const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
  const jiraClient = new JiraClientImpl(config);

  try {
    // Listar todas as tarefas do projeto TRELLO
    const tasks = await jiraClient.getTasks();
    console.log('Tasks:', tasks.map(task => task.title));

    // Criar uma nova tarefa
    const newTask = await jiraClient.createTask('New Bug');
    console.log('Created task:', newTask.title);

    // Atualizar a tarefa criada
    await jiraClient.updateTask(newTask.id, 'Updated Bug');
    console.log('Updated task:', newTask.title);

    // Deletar a tarefa criada
    await jiraClient.deleteTask(newTask.id);
    console.log('Deleted task:', newTask.title);
  } catch (error) {
    console.error('An error occurred:', error);
  }
}

// Executa a função main() se o script for executado como um módulo principal
if (require.main === module) {
  main();
}