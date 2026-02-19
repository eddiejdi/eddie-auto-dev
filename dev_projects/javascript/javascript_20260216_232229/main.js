const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JiraClient {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async getIssue(issueKey) {
    const response = await axios.get(`${this.url}/rest/api/2/issue/${issueKey}`);
    return response.data;
  }

  async createIssue(fields) {
    const response = await axios.post(`${this.url}/rest/api/2/issue`, fields);
    return response.data;
  }
}

class JavaScriptAgent {
  constructor(url, token) {
    this.url = url;
    this.token = token;
  }

  async trackActivity(issueKey, activityType, details) {
    const response = await axios.post(`${this.url}/rest/api/2/activity`, {
      issue: issueKey,
      type: activityType,
      details: JSON.stringify(details),
    });
    return response.data;
  }
}

class JiraScrum9 {
  constructor(jiraClient, javascriptAgent) {
    this.jiraClient = jiraClient;
    this.javascriptAgent = javascriptAgent;
  }

  async main() {
    try {
      const issueKey = 'ABC-123';
      const fields = {
        project: { key: 'PROJ' },
        summary: 'Teste JavaScript Agent',
        description: 'Ajustes para o JavaScript Agent',
        priority: { name: 'High' },
        assignee: { id: 'USER-ID' },
      };

      await this.jiraClient.createIssue(fields);

      const activityType = 'LOG';
      const details = {
        message: 'Iniciando monitoramento de atividades',
      };

      await this.javascriptAgent.trackActivity(issueKey, activityType, details);
    } catch (error) {
      console.error('Error:', error);
    }
  }
}

// Exemplo de uso
(async () => {
  const jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'YOUR-JIRA-TOKEN');
  const javascriptAgent = new JavaScriptAgent('https://your-javascript-agent-instance.com', 'YOUR-JAVASCRIPT-AGENT-TOKEN');

  const jiraScrum9 = new JiraScrum9(jiraClient, javascriptAgent);
  await jiraScrum9.main();
})();