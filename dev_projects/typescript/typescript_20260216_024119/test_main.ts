import axios from 'axios';

class JiraClient {
  private apiUrl: string;
  private accessToken: string;

  constructor(apiUrl: string, accessToken: string) {
    this.apiUrl = apiUrl;
    this.accessToken = accessToken;
  }

  async getIssues(query: string): Promise<any[]> {
    const response = await axios.get(`${this.apiUrl}/rest/api/2/search`, {
      params: { jql: query },
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data.issues;
  }

  async createIssue(issueData: any): Promise<any> {
    const response = await axios.post(`${this.apiUrl}/rest/api/2/issue`, issueData, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }

  async updateIssue(issueId: string, issueData: any): Promise<any> {
    const response = await axios.put(`${this.apiUrl}/rest/api/2/issue/${issueId}`, issueData, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }

  async deleteIssue(issueId: string): Promise<any> {
    const response = await axios.delete(`${this.apiUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }
}

// Função principal para executar o código
async function main() {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-access-token');

  try {
    // Caso de sucesso com valores válidos
    const issues = await jiraClient.getIssues('status = "To Do"');
    console.log('Tarefas:', issues);

    // Caso de erro (divisão por zero, valores inválidos, etc)
    const invalidQuery = 'status = "Invalid Status"';
    const error = await jiraClient.getIssues(invalidQuery);
    console.error('Erro ao consultar tarefas inválidas:', error);

    // Edge case (valores limite, strings vazias, None, etc)
    const emptyQuery = '';
    const emptyResponse = await jiraClient.getIssues(emptyQuery);
    console.log('Resposta vazia para consulta vazia:', emptyResponse);

    // Caso de sucesso com valores válidos
    const newIssueData = {
      fields: {
        project: { key: 'YOUR-PROJECT-KEY' },
        summary: 'Novo Tarefa',
        description: 'Descrição da nova tarefa',
        issuetype: { name: 'Task' }
      }
    };
    const newIssue = await jiraClient.createIssue(newIssueData);
    console.log('Nova Tarefa:', newIssue);

    // Caso de sucesso com valores válidos
    const issueIdToUpdate = 'YOUR-ISSUE-ID';
    const updatedIssueData = {
      fields: {
        summary: 'Tarefa Atualizada'
      }
    };
    await jiraClient.updateIssue(issueIdToUpdate, updatedIssueData);
    console.log('Tarefa Atualizada:', await jiraClient.getIssues(`id = ${issueIdToUpdate}`));

    // Caso de sucesso com valores válidos
    const issueToDelete = 'YOUR-ISSUE-ID';
    await jiraClient.deleteIssue(issueToDelete);
    console.log('Tarefa Excluída:', await jiraClient.getIssues(`id = ${issueToDelete}`));
  } catch (error) {
    console.error('Erro:', error);
  }
}

// Executa a função principal
main();