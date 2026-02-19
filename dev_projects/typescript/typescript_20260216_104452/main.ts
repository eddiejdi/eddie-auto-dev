// Importações necessárias
import axios from 'axios';
import { JiraClient } from '@jira/client';

// Interface para representar uma tarefa do Jira
interface Task {
  id: string;
  summary: string;
  status: string;
}

// Classe para representar o cliente do TypeScript Agent
class TypeScriptAgentClient {
  private jiraClient: JiraClient;

  constructor(apiToken: string, baseUrl: string) {
    this.jiraClient = new JiraClient({
      auth: { token: apiToken },
      baseUrl,
    });
  }

  // Função para criar uma nova tarefa no Jira
  async createTask(summary: string): Promise<Task> {
    const response = await this.jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' }, // Substitua pelo código do projeto
        summary,
        description: 'Criado por TypeScript Agent',
        issuetype: { name: 'Task' },
      },
    });

    return response.data;
  }

  // Função para atualizar a situação de uma tarefa no Jira
  async updateTaskStatus(taskId: string, status: string): Promise<void> {
    await this.jiraClient.updateIssue({
      issueKey: taskId,
      fields: { status },
    });
  }
}

// Função principal do programa
async function main() {
  const apiToken = 'YOUR_JIRA_API_TOKEN';
  const baseUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  const agentClient = new TypeScriptAgentClient(apiToken, baseUrl);

  try {
    // Criar uma nova tarefa no Jira
    const task = await agentClient.createTask('Implemente um sistema de tipos avançado em TypeScript');
    console.log(`Tarefa criada com ID: ${task.id}`);

    // Atualizar a situação da tarefa para 'In Progress'
    await agentClient.updateTaskStatus(task.id, 'In Progress');
    console.log(`Tarefa atualizada para 'In Progress'`);

    // Exemplo de uso de generics
    const numbers = [1, 2, 3, 4, 5];
    const doubledNumbers: number[] = numbers.map(num => num * 2);
    console.log('Números dobrados:', doubledNumbers);

    // Exemplo de utility types
    type Person = { name: string; age: number };
    const person: Person = { name: 'John Doe', age: 30 };

    console.log('Nome do pessoa:', person.name);
    console.log('Idade da pessoa:', person.age);
  } catch (error) {
    console.error('Erro ao executar o programa:', error);
  }
}

// Executa a função principal se o script for executado diretamente
if (require.main === module) {
  main();
}