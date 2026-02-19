// Importações necessárias
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async createIssue(title, description) {
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Task' }
      }
    };

    try {
      const response = await axios.post(`${this.url}/rest/api/2/issue`, issueData, {
        headers: {
          Authorization: `Basic ${btoa(`${this.token}:`)}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(issueId, title, description) {
    const issueData = {
      fields: {
        summary: title,
        description: description
      }
    };

    try {
      const response = await axios.put(`${this.url}/rest/api/2/issue/${issueId}`, issueData, {
        headers: {
          Authorization: `Basic ${btoa(`${this.token}:`)}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async getIssue(issueId) {
    try {
      const response = await axios.get(`${this.url}/rest/api/2/issue/${issueId}`, {
        headers: {
          Authorization: `Basic ${btoa(`${this.token}:`)}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error getting issue:', error);
      throw error;
    }
  }

  async getIssuesByProject(projectKey) {
    try {
      const response = await axios.get(`${this.url}/rest/api/2/search`, {
        params: {
          jql: `project=${projectKey}`,
          fields: ['key', 'summary']
        },
        headers: {
          Authorization: `Basic ${btoa(`${this.token}:`)}`,
          'Content-Type': 'application/json'
        }
      });

      return response.data;
    } catch (error) {
      console.error('Error getting issues by project:', error);
      throw error;
    }
  }
}

class JavaScriptAgent {
  constructor(url, token) {
    this.url = url;
    this.token = token;
    this.jiraClient = new JiraClient(this.url, this.token);
  }

  async trackActivity(issueId, activityType, description) {
    try {
      const issueData = {
        fields: {
          customfield_10101: { value: activityType }, // Exemplo de campo personalizado
          comment: {
            body: description,
            author: {
              name: 'JavaScript Agent'
            }
          }
        }
      };

      await this.jiraClient.updateIssue(issueId, '', JSON.stringify(issueData));
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }

  async getIssues() {
    try {
      const issues = await this.jiraClient.getIssuesByProject('YOUR_PROJECT_KEY');
      return issues;
    } catch (error) {
      console.error('Error getting issues:', error);
      throw error;
    }
  }
}

async function main() {
  const agent = new JavaScriptAgent('https://your-jira-instance.atlassian.net', 'YOUR_JIRA_TOKEN');

  try {
    // Criar uma nova tarefa
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: 'Teste de atividade',
        description: 'Este é um teste de atividade do JavaScript Agent',
        issuetype: { name: 'Task' }
      }
    };

    const newIssue = await agent.jiraClient.createIssue(issueData.title, issueData.description);
    console.log('New issue created:', newIssue);

    // Atualizar a tarefa
    await agent.trackActivity(newIssue.key, 'Update', 'Atividade atualizada pelo JavaScript Agent');

    // Listar todas as tarefas do projeto
    const issues = await agent.getIssues();
    console.log('Issues in project:', issues);
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}