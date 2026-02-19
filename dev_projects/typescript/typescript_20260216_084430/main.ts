// Importações necessárias
import axios from 'axios';
import { JiraClient } from '@jira/client';

// Definição da classe JiraClientTypeScript
class JiraClientTypeScript {
  private client: JiraClient;

  constructor(token: string, baseUrl: string) {
    this.client = new JiraClient({
      auth: token,
      baseUrl,
    });
  }

  // Função para criar uma tarefa
  async createIssue(title: string, description: string): Promise<void> {
    try {
      await this.client.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' },
        },
      });
      console.log('Tarefa criada com sucesso!');
    } catch (error) {
      console.error('Erro ao criar tarefa:', error);
    }
  }

  // Função para listar todas as tarefas
  async listIssues(): Promise<void> {
    try {
      const issues = await this.client.search({
        jql: 'project = YOUR_PROJECT_KEY',
        fields: ['summary', 'description'],
      });
      console.log('Tarefas listadas:');
      issues.forEach(issue => {
        console.log(`- ${issue.fields.summary}`);
      });
    } catch (error) {
      console.error('Erro ao listar tarefas:', error);
    }
  }

  // Função para atualizar uma tarefa
  async updateIssue(id: string, title: string, description: string): Promise<void> {
    try {
      await this.client.updateIssue({
        issueIdOrKey: id,
        fields: {
          summary: title,
          description: description,
        },
      });
      console.log('Tarefa atualizada com sucesso!');
    } catch (error) {
      console.error('Erro ao atualizar tarefa:', error);
    }
  }

  // Função para deletar uma tarefa
  async deleteIssue(id: string): Promise<void> {
    try {
      await this.client.deleteIssue({
        issueIdOrKey: id,
      });
      console.log('Tarefa deletada com sucesso!');
    } catch (error) {
      console.error('Erro ao deletar tarefa:', error);
    }
  }
}

// Função main para executar o código
async function main() {
  const token = 'YOUR_JIRA_TOKEN';
  const baseUrl = 'https://your-jira-instance.atlassian.net';

  const jiraClient = new JiraClientTypeScript(token, baseUrl);

  try {
    // Criar uma tarefa
    await jiraClient.createIssue('Novo Título', 'Nova descrição');

    // Listar todas as tarefas
    await jiraClient.listIssues();

    // Atualizar uma tarefa
    await jiraClient.updateIssue('ISSUE_ID', 'Novo título atualizado', 'Nova descrição atualizada');

    // Deletar uma tarefa
    await jiraClient.deleteIssue('ISSUE_ID');
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Verifica se o código é executado como um módulo principal
if (require.main === module) {
  main();
}