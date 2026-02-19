// Importações necessárias
const axios = require('axios');
const { exec } = require('child_process');

// Classe para representar uma tarefa
class Task {
  constructor(id, name) {
    this.id = id;
    this.name = name;
    this.status = 'pending';
  }

  // Função para atualizar o status da tarefa
  updateStatus(status) {
    this.status = status;
  }
}

// Classe para representar a integração com Jira
class JiraIntegration {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  // Função para criar uma tarefa no Jira
  async createTask(task) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/task`, task);
      return response.data.id;
    } catch (error) {
      console.error('Error creating task:', error);
      throw error;
    }
  }

  // Função para atualizar o status da tarefa no Jira
  async updateTaskStatus(taskId, status) {
    try {
      const response = await axios.put(`${this.jiraUrl}/rest/api/2/task/${taskId}`, { status });
      return response.data.id;
    } catch (error) {
      console.error('Error updating task status:', error);
      throw error;
    }
  }
}

// Função principal para executar a integração
async function main() {
  try {
    // Configurações do JavaScript Agent
    const agentConfig = {
      url: 'http://localhost:9200',
      token: 'your_token_here'
    };

    // Configurações do Jira
    const jiraUrl = 'https://your_jira_url.com';
    const username = 'your_username_here';
    const password = 'your_password_here';

    // Instancia das classes
    const task = new Task(1, 'Example Task');
    const jiraIntegration = new JiraIntegration(jiraUrl, username, password);

    // Cria a tarefa no Jira
    const taskId = await jiraIntegration.createTask(task);
    console.log('Task created with ID:', taskId);

    // Atualiza o status da tarefa no Jira
    await jiraIntegration.updateTaskStatus(taskId, 'in_progress');
    console.log('Task updated to in progress');

    // Executa um comando em um shell
    exec('ls -l', (error, stdout, stderr) => {
      if (error) {
        console.error(`Error executing command: ${error.message}`);
      } else {
        console.log(`stdout: ${stdout}`);
      }
      if (stderr) {
        console.error(`stderr: ${stderr}`);
      }
    });

    // Finaliza a execução
    console.log('Execution finished');
  } catch (error) {
    console.error('Error:', error);
  }
}

// Executa a função principal
if (require.main === module) {
  main();
}