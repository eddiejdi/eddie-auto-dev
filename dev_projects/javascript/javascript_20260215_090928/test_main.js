const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

// Função para enviar um evento ao Jira
async function sendEventToJira(event) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/event', event);
    console.log('Evento enviado com sucesso:', response.data);
  } catch (error) {
    console.error('Erro ao enviar evento para Jira:', error);
  }
}

// Função para gerenciar tarefas
class TaskManager {
  constructor() {
    this.tasks = [];
  }

  addTask(task) {
    this.tasks.push(task);
  }

  getTasks() {
    return this.tasks;
  }
}

// Função principal do programa
async function main() {
  // Cria uma instância de TaskManager
  const taskManager = new TaskManager();

  // Adiciona algumas tarefas
  taskManager.addTask({ id: uuidv4(), name: 'Tarefa 1', status: 'Iniciada' });
  taskManager.addTask({ id: uuidv4(), name: 'Tarefa 2', status: 'Pendente' });

  // Monitora as tarefas
  setInterval(() => {
    const tasks = taskManager.getTasks();
    console.log('Tarefas atuais:');
    tasks.forEach(task => console.log(`- ${task.name} (${task.status})`));
  }, 2000);

  // Simula um evento de atividade
  const event = {
    id: uuidv4(),
    type: 'activity',
    data: { message: 'Tarefa 1 concluída' }
  };

  // Envia o evento para Jira
  await sendEventToJira(event);
}

// Executa a função main()
if (require.main === module) {
  main();
}