// Importações necessárias
import axios from 'axios';

// Definição da classe JiraClient para interagir com a API do Jira
class JiraClient {
  private apiUrl: string;
  private accessToken: string;

  constructor(apiUrl: string, accessToken: string) {
    this.apiUrl = apiUrl;
    this.accessToken = accessToken;
  }

  async fetchIssues(query: string): Promise<any[]> {
    try {
      const response = await axios.get(`${this.apiUrl}/rest/api/2/search`, {
        params: { jql: query },
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      return response.data.issues;
    } catch (error) {
      console.error('Erro ao buscar tarefas:', error);
      throw error;
    }
  }

  async createIssue(issue: any): Promise<any> {
    try {
      const response = await axios.post(`${this.apiUrl}/rest/api/2/issue`, issue, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      return response.data;
    } catch (error) {
      console.error('Erro ao criar tarefa:', error);
      throw error;
    }
  }

  async updateIssue(issueId: string, issue: any): Promise<any> {
    try {
      const response = await axios.put(`${this.apiUrl}/rest/api/2/issue/${issueId}`, issue, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      return response.data;
    } catch (error) {
      console.error('Erro ao atualizar tarefa:', error);
      throw error;
    }
  }

  async deleteIssue(issueId: string): Promise<any> {
    try {
      const response = await axios.delete(`${this.apiUrl}/rest/api/2/issue/${issueId}`, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`
        }
      });
      return response.data;
    } catch (error) {
      console.error('Erro ao deletar tarefa:', error);
      throw error;
    }
  }

  async logError(error: any): Promise<void> {
    try {
      const issue = {
        fields: {
          summary: 'Erro de integração com Jira',
          description: `Erro: ${error.message}`,
          priority: { name: 'High' },
          status: { name: 'To Do' }
        }
      };
      await this.createIssue(issue);
    } catch (error) {
      console.error('Erro ao registrar log de erro:', error);
    }
  }
}

// Função main para executar o código
async function main() {
  const jiraClient = new JiraClient(
    'https://your-jira-instance.atlassian.net/rest/api/2',
    'your-access-token'
  );

  try {
    // Exemplo de busca de tarefas
    const issues = await jiraClient.fetchIssues('project=YOUR_PROJECT');
    console.log('Tarefas encontradas:', issues);

    // Exemplo de criação de tarefa
    const newIssue = {
      fields: {
        project: { key: 'YOUR_PROJECT' },
        summary: 'Novo teste',
        description: 'Este é um novo teste para a integração com Jira.',
        priority: { name: 'High' },
        status: { name: 'To Do' }
      }
    };
    const createdIssue = await jiraClient.createIssue(newIssue);
    console.log('Tarefa criada:', createdIssue);

    // Exemplo de atualização de tarefa
    const issueId = 'YOUR_ISSUE_ID';
    const updatedIssue = {
      fields: {
        summary: 'Atualizado teste'
      }
    };
    await jiraClient.updateIssue(issueId, updatedIssue);
    console.log('Tarefa atualizada:', updatedIssue);

    // Exemplo de deleção de tarefa
    const deletedIssue = await jiraClient.deleteIssue(issueId);
    console.log('Tarefa deletada:', deletedIssue);

    // Exemplo de registro de log de erro
    try {
      throw new Error('Teste de erro');
    } catch (error) {
      await jiraClient.logError(error);
    }
  } catch (error) {
    console.error('Erro principal:', error);
  }
}

// Executa a função main
main();