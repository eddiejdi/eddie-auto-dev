// Importações necessárias
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Configuração do Jira Client
const jiraClient = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

// Função para criar um novo item na tarefa
async function createTask(title, description) {
  try {
    const task = await jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    });
    console.log('Task created:', task);
  } catch (error) {
    console.error('Error creating task:', error);
  }
}

// Função para atualizar um item na tarefa
async function updateTask(taskId, title, description) {
  try {
    const updatedTask = await jiraClient.updateIssue({
      issueKey: taskId,
      fields: {
        summary: title,
        description: description
      }
    });
    console.log('Task updated:', updatedTask);
  } catch (error) {
    console.error('Error updating task:', error);
  }
}

// Função para deletar um item na tarefa
async function deleteTask(taskId) {
  try {
    await jiraClient.deleteIssue({ issueKey: taskId });
    console.log('Task deleted');
  } catch (error) {
    console.error('Error deleting task:', error);
  }
}

// Função principal
async function main() {
  // Criar uma nova tarefa
  const newTaskTitle = 'Teste de Tarefa';
  const newTaskDescription = 'Este é um teste de criação de tarefa.';
  await createTask(newTaskTitle, newTaskDescription);

  // Atualizar a tarefa criada
  const taskId = 'YOUR_TASK_ID'; // Substitua pelo ID da tarefa criada
  const updatedTaskTitle = 'Teste de Tarefa Atualizada';
  const updatedTaskDescription = 'Este é um teste de atualização de tarefa.';
  await updateTask(taskId, updatedTaskTitle, updatedTaskDescription);

  // Deletar a tarefa criada
  await deleteTask(taskId);
}

// Executar o código principal
if (require.main === module) {
  main();
}