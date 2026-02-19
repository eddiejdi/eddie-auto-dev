// Importações necessárias
import axios from 'axios';

// Definição da classe JiraClient para interagir com a API do Jira
class JiraClient {
  private apiKey: string;
  private apiUrl: string;

  constructor(apiKey: string, apiUrl: string) {
    this.apiKey = apiKey;
    this.apiUrl = apiUrl;
  }

  async fetchIssues(): Promise<any[]> {
    try {
      const response = await axios.get(`${this.apiUrl}/rest/api/2/search`, {
        params: {
          jql: 'project = MyProject AND status = In Progress',
          fields: ['summary', 'status'],
          maxResults: 10,
        },
        headers: {
          'Authorization': `Basic ${btoa(this.apiKey)}`,
        },
      });

      return response.data.issues;
    } catch (error) {
      console.error('Error fetching issues:', error);
      throw error;
    }
  }

  async updateIssue(issueId: string, summary: string): Promise<any> {
    try {
      const response = await axios.put(`${this.apiUrl}/rest/api/2/issue/${issueId}`, {
        fields: {
          summary,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }
}

// Função principal para executar a integração
async function main() {
  const apiKey = 'your-jira-api-key';
  const apiUrl = 'https://your-jira-instance.atlassian.net';

  const jiraClient = new JiraClient(apiKey, apiUrl);

  try {
    const issues = await jiraClient.fetchIssues();
    console.log('Fetched issues:', issues);

    // Exemplo de atualização de uma tarefa
    const issueId = 'ABC123';
    const summaryUpdate = 'Updated task summary';
    const updatedIssue = await jiraClient.updateIssue(issueId, summaryUpdate);
    console.log('Updated issue:', updatedIssue);
  } catch (error) {
    console.error('Main function failed:', error);
  }
}

// Verifica se o script é executado como um módulo principal
if (require.main === module) {
  main();
}