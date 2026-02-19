import axios from 'axios';

// Define a interface para uma tarefa
interface Task {
  id: number;
  title: string;
  description: string;
}

// Define a classe JiraClient para interagir com o Jira API
class JiraClient {
  private apiUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';

  constructor(private token: string) {}

  async createTask(task: Task): Promise<Task> {
    try {
      const response = await axios.post(`${this.apiUrl}/issue`, task, {
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create task: ${error.message}`);
    }
  }

  async getTasks(): Promise<Task[]> {
    try {
      const response = await axios.get(`${this.apiUrl}/issue`, {
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data.map((item) => ({
        id: item.id,
        title: item.fields.summary,
        description: item.fields.description,
      }));
    } catch (error) {
      throw new Error(`Failed to get tasks: ${error.message}`);
    }
  }

  async updateTask(taskId: number, updates: Partial<Task>): Promise<Task> {
    try {
      const response = await axios.put(`${this.apiUrl}/issue/${taskId}`, updates, {
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update task: ${error.message}`);
    }
  }

  async deleteTask(taskId: number): Promise<void> {
    try {
      await axios.delete(`${this.apiUrl}/issue/${taskId}`, {
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      });
    } catch (error) {
      throw new Error(`Failed to delete task: ${error.message}`);
    }
  }
}

// Define a classe TaskManager para gerenciar as tarefas
class TaskManager {
  private client: JiraClient;

  constructor(token: string) {
    this.client = new JiraClient(token);
  }

  async createTask(task: Task): Promise<Task> {
    return await this.client.createTask(task);
  }

  async getTasks(): Promise<Task[]> {
    return await this.client.getTasks();
  }

  async updateTask(taskId: number, updates: Partial<Task>): Promise<Task> {
    return await this.client.updateTask(taskId, updates);
  }

  async deleteTask(taskId: number): Promise<void> {
    await this.client.deleteTask(taskId);
  }
}

// Função main para executar o programa
async function main() {
  const token = 'your-jira-token';
  const taskManager = new TaskManager(token);

  try {
    // Criar uma nova tarefa
    const newTask: Task = {
      id: null,
      title: 'Implement TypeScript Agent with Jira',
      description: 'Automate the registration of tasks and monitor activities.',
    };
    const createdTask = await taskManager.createTask(newTask);
    console.log('Created task:', createdTask);

    // Listar todas as tarefas
    const tasks = await taskManager.getTasks();
    console.log('Tasks:', tasks);

    // Atualizar uma tarefa existente
    const taskIdToUpdate = 12345; // Replace with the actual task ID
    const updatedTask: Partial<Task> = {
      title: 'Update TypeScript Agent with Jira',
    };
    await taskManager.updateTask(taskIdToUpdate, updatedTask);
    console.log('Updated task:', tasks);

    // Excluir uma tarefa
    const taskIdToDelete = 12346; // Replace with the actual task ID
    await taskManager.deleteTask(taskIdToDelete);
    console.log('Deleted task:', tasks);
  } catch (error) {
    console.error(error.message);
  }
}

// Execute a função main
if (require.main === module) {
  main();
}