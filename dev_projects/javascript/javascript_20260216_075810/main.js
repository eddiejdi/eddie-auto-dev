const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Classe para representar uma tarefa
class Task {
  constructor(id, title) {
    this.id = id;
    this.title = title;
    this.status = 'Open';
  }

  updateStatus(status) {
    this.status = status;
  }
}

// Classe para representar um bug
class Bug {
  constructor(id, title, description) {
    this.id = id;
    this.title = title;
    this.description = description;
    this.status = 'Open';
  }

  updateStatus(status) {
    this.status = status;
  }
}

// Classe para representar uma atividade (tarefa ou bug)
class Activity {
  constructor(task, status) {
    this.task = task;
    this.status = status;
  }
}

// Classe para representar o JavaScript Agent
class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async getTasks() {
    const tasks = await this.jiraClient.getIssues({
      fields: ['id', 'title'],
      status: 'open',
    });
    return tasks.map(task => new Task(task.id, task.fields.title));
  }

  async updateTaskStatus(id, status) {
    const updatedTask = await this.jiraClient.updateIssue(id, { fields: { status } });
    return new Task(updatedTask.id, updatedTask.fields.title);
  }

  async getBugs() {
    const bugs = await this.jiraClient.getIssues({
      fields: ['id', 'title', 'description'],
      status: 'open',
    });
    return bugs.map(bug => new Bug(bug.id, bug.fields.title, bug.fields.description));
  }

  async updateBugStatus(id, status) {
    const updatedBug = await this.jiraClient.updateIssue(id, { fields: { status } });
    return new Bug(updatedBug.id, updatedBug.fields.title, updatedBug.fields.description);
  }
}

// Função principal
async function main() {
  // Configuração do Jira Client
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net',
    username: 'your-username',
    password: 'your-password',
  });

  // Instancia o JavaScript Agent
  const agent = new JavaScriptAgent(jiraClient);

  try {
    console.log('Tasks:');
    const tasks = await agent.getTasks();
    tasks.forEach(task => console.log(`- ${task.title} (${task.status})`));

    console.log('\nBugs:');
    const bugs = await agent.getBugs();
    bugs.forEach(bug => console.log(`- ${bug.title} (${bug.status})`));
  } catch (error) {
    console.error('Error:', error);
  }
}

// Executa a função principal
if (require.main === module) {
  main();
}