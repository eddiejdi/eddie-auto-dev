const axios = require('axios');
const { createClient } = require('@elastic/elasticsearch');

// Configuração do Elasticsearch
const esClient = createClient({
  node: 'http://localhost:9200'
});

// Função para criar um novo projeto no Jira
async function createProject(projectName) {
  const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/project', {
    name: projectName,
    description: `Projeto criado por JavaScript Agent`
  });
  return response.data;
}

// Função para criar uma nova tarefa no Jira
async function createTask(projectId, taskName) {
  const response = await axios.post(`https://your-jira-instance.atlassian.net/rest/api/3/task`, {
    project: projectId,
    name: taskName,
    description: `Tarefa criada por JavaScript Agent`
  });
  return response.data;
}

// Função para atualizar a descrição de uma tarefa no Jira
async function updateTask(taskId, newDescription) {
  const response = await axios.put(`https://your-jira-instance.atlassian.net/rest/api/3/task/${taskId}`, {
    description: newDescription
  });
  return response.data;
}

// Função para listar todas as tarefas de um projeto no Jira
async function listTasks(projectId) {
  const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/3/task/search`, {
    projectKey: projectId,
    fields: ['id', 'name', 'description']
  });
  return response.data;
}

// Função para listar todos os projetos no Jira
async function listProjects() {
  const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/3/project/search`, {
    fields: ['id', 'key', 'name']
  });
  return response.data;
}

// Função principal para executar as tarefas de monitoramento
async function main() {
  try {
    // Criar um novo projeto
    const project = await createProject('My JavaScript Project');
    console.log(`Projeto criado: ${project.name}`);

    // Criar uma nova tarefa no projeto
    const task = await createTask(project.id, 'Monitoramento de atividades');
    console.log(`Tarefa criada: ${task.name}`);

    // Atualizar a descrição da tarefa
    await updateTask(task.id, 'Atualizada para monitorar atividades em tempo real');
    console.log(`Descrição atualizada`);

    // Listar todas as tarefas do projeto
    const tasks = await listTasks(project.id);
    console.log(`Tarefas no projeto:`);
    tasks.forEach(task => {
      console.log(`${task.name}`);
    });

    // Listar todos os projetos
    const allProjects = await listProjects();
    console.log(`Projetos disponíveis:`);
    allProjects.forEach(project => {
      console.log(`${project.key}: ${project.name}`);
    });
  } catch (error) {
    console.error('Ocorreu um erro:', error);
  }
}

// Executa a função principal
if (require.main === module) {
  main();
}