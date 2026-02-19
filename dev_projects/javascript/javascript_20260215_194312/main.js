// Importações necessárias
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async login() {
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/session`, {
      username: this.username,
      password: this.password
    });
    return response.data.session.token;
  }

  async createIssue(projectKey, issueType, fields) {
    const token = await this.login();
    const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, {
      fields: {
        project: { key: projectKey },
        issuetype: { name: issueType }
      },
      body: {
        fields: fields
      }
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }

  async updateIssue(issueId, fields) {
    const token = await this.login();
    const response = await axios.put(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      fields: fields
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }

  async getIssue(issueId) {
    const token = await this.login();
    const response = await axios.get(`${this.jiraUrl}/rest/api/2/issue/${issueId}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response.data;
  }
}

class JavaScriptAgent {
  constructor(jiraClient) {
    this.jiraClient = jiraClient;
  }

  async trackActivity(projectKey, issueType, fields) {
    const issueId = uuidv4();
    const issue = await this.jiraClient.createIssue(projectKey, issueType, fields);
    console.log(`Created issue: ${issue.key}`);
    return issue.id;
  }

  async updateActivity(issueId, fields) {
    const updatedFields = { ...fields };
    const issue = await this.jiraClient.updateIssue(issueId, updatedFields);
    console.log(`Updated issue: ${issue.key}`);
    return issue.id;
  }

  async getActivity(issueId) {
    const issue = await this.jiraClient.getIssue(issueId);
    console.log(`Activity for issue ${issue.key}:`);
    console.log(issue.fields);
    return issue.id;
  }
}

// Função main para executar o script
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraClient = new JiraClient(jiraUrl, username, password);
  const javascriptAgent = new JavaScriptAgent(jiraClient);

  try {
    // Criar uma nova atividade
    const issueId = await javascriptAgent.trackActivity('YOUR-PROJECT-KEY', 'Task', { summary: 'New task' });

    // Atualizar a atividade
    await javascriptAgent.updateActivity(issueId, { description: 'Updated task description' });

    // Obter a atividade atualizada
    const activity = await javascriptAgent.getActivity(issueId);
    console.log('Activity updated:', activity);

    // Exibir uma mensagem de sucesso
    console.log('All activities tracked successfully!');
  } catch (error) {
    console.error('Error tracking activities:', error);
  }
}

// Executar a função main
if (require.main === module) {
  main();
}