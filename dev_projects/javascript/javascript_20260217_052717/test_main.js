const axios = require('axios');
const fs = require('fs');

// Classe para representar uma tarefa
class Task {
  constructor(id, name, description) {
    this.id = id;
    this.name = name;
    this.description = description;
  }
}

// Classe para representar um relatório
class Report {
  constructor(title, tasks) {
    this.title = title;
    this.tasks = tasks;
  }
}

// Função para enviar uma requisição POST para Jira
async function sendJiraRequest(url, data) {
  try {
    const response = await axios.post(url, data);
    return response.data;
  } catch (error) {
    throw new Error(`Erro ao enviar requisição: ${error.message}`);
  }
}

// Função para criar um relatório
async function createReport(title, tasks) {
  const report = new Report(title, tasks);
  const reportData = JSON.stringify(report);

  try {
    const response = await sendJiraRequest('https://your-jira-instance.atlassian.net/rest/api/3/project/12345/report', reportData);
    return response;
  } catch (error) {
    throw new Error(`Erro ao criar relatório: ${error.message}`);
  }
}

// Função para monitorar atividades
async function monitorActivities() {
  try {
    const response = await sendJiraRequest('https://your-jira-instance.atlassian.net/rest/api/3/project/12345/activity', {});
    return response;
  } catch (error) {
    throw new Error(`Erro ao monitorar atividades: ${error.message}`);
  }
}

// Função para gerenciar tarefas
async function manageTasks() {
  try {
    const tasks = await monitorActivities();
    const reportTitle = 'Atividades do Projeto';
    const reportData = tasks.map(task => ({
      id: task.id,
      name: task.name,
      description: task.description,
    }));

    const report = new Report(reportTitle, reportData);
    const reportResponse = await createReport(reportTitle, report.tasks);

    console.log('Relatório criado com sucesso:', reportResponse);
  } catch (error) {
    console.error('Erro ao gerenciar tarefas:', error.message);
  }
}

// Função principal
async function main() {
  try {
    const tasks = await monitorActivities();
    const reportTitle = 'Atividades do Projeto';
    const reportData = tasks.map(task => ({
      id: task.id,
      name: task.name,
      description: task.description,
    }));

    const report = new Report(reportTitle, reportData);
    const reportResponse = await createReport(reportTitle, report.tasks);

    console.log('Relatório criado com sucesso:', reportResponse);
  } catch (error) {
    console.error('Erro ao gerenciar tarefas:', error.message);
  }
}

// Execução da função principal
if (require.main === module) {
  main();
}