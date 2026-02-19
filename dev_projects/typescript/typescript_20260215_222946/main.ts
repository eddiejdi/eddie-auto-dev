import axios from 'axios';

// Define a classe JiraClient para interagir com a API do Jira
class JiraClient {
  private apiUrl: string;
  private token: string;

  constructor(apiUrl: string, token: string) {
    this.apiUrl = apiUrl;
    this.token = token;
  }

  async getIssues(query: string): Promise<any[]> {
    const response = await axios.get(`${this.apiUrl}/rest/api/3/search`, {
      params: { jql: query },
      headers: {
        'Authorization': `Basic ${btoa(`${this.token}:x`)}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data.issues;
  }

  async createIssue(issueData: any): Promise<any> {
    const response = await axios.post(`${this.apiUrl}/rest/api/3/issue`, issueData, {
      headers: {
        'Authorization': `Basic ${btoa(`${this.token}:x`)}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }

  async updateIssue(issueId: string, issueData: any): Promise<any> {
    const response = await axios.put(`${this.apiUrl}/rest/api/3/issue/${issueId}`, issueData, {
      headers: {
        'Authorization': `Basic ${btoa(`${this.token}:x`)}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }

  async deleteIssue(issueId: string): Promise<any> {
    const response = await axios.delete(`${this.apiUrl}/rest/api/3/issue/${issueId}`, {
      headers: {
        'Authorization': `Basic ${btoa(`${this.token}:x`)}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data;
  }
}

// Define a classe ScrumBoard para gerenciar tarefas em Scrum
class ScrumBoard {
  private issues: any[];
  private client: JiraClient;

  constructor(client: JiraClient) {
    this.client = client;
    this.issues = [];
  }

  async fetchIssues(query: string): Promise<any[]> {
    const issues = await this.client.getIssues(query);
    this.issues = issues;
    return issues;
  }

  async createIssue(issueData: any): Promise<any> {
    const issue = await this.client.createIssue(issueData);
    this.issues.push(issue);
    return issue;
  }

  async updateIssue(issueId: string, issueData: any): Promise<any> {
    const updatedIssue = await this.client.updateIssue(issueId, issueData);
    this.issues = this.issues.map((issue) => (issue.key === issueId ? updatedIssue : issue));
    return updatedIssue;
  }

  async deleteIssue(issueId: string): Promise<any> {
    const deletedIssue = await this.client.deleteIssue(issueId);
    this.issues = this.issues.filter((issue) => issue.key !== issueId);
    return deletedIssue;
  }
}

// Define a classe ScrumProject para gerenciar projetos em Scrum
class ScrumProject {
  private name: string;
  private board: ScrumBoard;

  constructor(name: string, board: ScrumBoard) {
    this.name = name;
    this.board = board;
  }

  async fetchIssues(query: string): Promise<any[]> {
    return await this.board.fetchIssues(query);
  }

  async createIssue(issueData: any): Promise<any> {
    return await this.board.createIssue(issueData);
  }

  async updateIssue(issueId: string, issueData: any): Promise<any> {
    return await this.board.updateIssue(issueId, issueData);
  }

  async deleteIssue(issueId: string): Promise<any> {
    return await this.board.deleteIssue(issueId);
  }
}

// Função main para executar o programa
async function main() {
  const apiUrl = 'https://your-jira-instance.atlassian.net';
  const token = 'your-jira-token';

  const client = new JiraClient(apiUrl, token);
  const board = new ScrumBoard(client);

  try {
    // Fetch issues from Jira
    const issues = await board.fetchIssues('status = open');
    console.log('Issues:', issues);

    // Create a new issue
    const newIssueData = {
      fields: {
        project: { key: 'YOUR-PROJECT-KEY' },
        summary: 'New Scrum Task',
        description: 'This is a new task for the Scrum project.',
        issuetype: { name: 'Task' }
      }
    };
    const newIssue = await board.createIssue(newIssueData);
    console.log('Created Issue:', newIssue);

    // Update an existing issue
    const updateIssueData = {
      fields: {
        description: 'This is an updated task for the Scrum project.'
      }
    };
    const updatedIssue = await board.updateIssue(newIssue.key, updateIssueData);
    console.log('Updated Issue:', updatedIssue);

    // Delete an issue
    await board.deleteIssue(newIssue.key);
    console.log('Deleted Issue');

  } catch (error) {
    console.error('Error:', error);
  }
}

// Execute the main function if this file is run as a script
if (require.main === module) {
  main();
}