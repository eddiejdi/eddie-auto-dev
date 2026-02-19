import axios from 'axios';

// Interface para representar uma tarefa em Jira
interface Task {
  id: number;
  summary: string;
  status: string;
}

// Função para criar uma nova tarefa no Jira
async function createTask(task: Task): Promise<Task> {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', task);
    return response.data as Task;
  } catch (error) {
    console.error('Error creating task:', error);
    throw error;
  }
}

// Função para atualizar uma tarefa no Jira
async function updateTask(task: Task): Promise<Task> {
  try {
    const response = await axios.put(`https://your-jira-instance.atlassian.net/rest/api/2/issue/${task.id}`, task);
    return response.data as Task;
  } catch (error) {
    console.error('Error updating task:', error);
    throw error;
  }
}

// Função para buscar uma tarefa pelo ID no Jira
async function getTask(taskId: number): Promise<Task> {
  try {
    const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/2/issue/${taskId}`);
    return response.data as Task;
  } catch (error) {
    console.error('Error getting task:', error);
    throw error;
  }
}

// Função para listar todas as tarefas do usuário no Jira
async function listTasks(): Promise<Task[]> {
  try {
    const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/2/myself/issue`);
    return response.data.map((issue: any) => ({
      id: issue.id,
      summary: issue.fields.summary,
      status: issue.fields.status.name
    }));
  } catch (error) {
    console.error('Error listing tasks:', error);
    throw error;
  }
}

// Função principal para executar o script
async function main() {
  try {
    // Criar uma nova tarefa
    const newTask = await createTask({
      fields: {
        project: { key: 'YOUR-PROJECT' },
        summary: 'Implement TypeScript integration with Jira',
        description: 'This task is to integrate TypeScript with Jira using the REST API.',
        issuetype: { name: 'Bug' }
      }
    });
    console.log('New task created:', newTask);

    // Atualizar uma tarefa
    const updatedTask = await updateTask({
      fields: {
        status: { name: 'In Progress' }
      },
      id: newTask.id
    });
    console.log('Updated task:', updatedTask);

    // Buscar uma tarefa pelo ID
    const task = await getTask(newTask.id);
    console.log('Task details:', task);

    // Listar todas as tarefas do usuário
    const tasks = await listTasks();
    console.log('All tasks:', tasks);
  } catch (error) {
    console.error('Error in main function:', error);
  }
}

// Executar a função principal se o script for chamado diretamente
if (require.main === module) {
  main();
}