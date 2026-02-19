const axios = require('axios');
const { promisify } = require('util');

// Função para enviar dados ao Jira via API
async function sendToJira(data) {
  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/3/issue', data, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${Buffer.from('username:password').toString('base64')}`
      }
    });
    console.log('Issue created successfully:', response.data);
  } catch (error) {
    console.error('Error creating issue:', error.response ? error.response.data : error.message);
  }
}

// Função para criar um novo issue no Jira
async function createIssue(title, description, projectKey) {
  try {
    const data = {
      fields: {
        project: { key: projectKey },
        summary: title,
        description: description,
        priority: { name: 'High' },
        assignee: { name: 'username' }
      }
    };
    await sendToJira(data);
  } catch (error) {
    console.error('Error creating issue:', error.response ? error.response.data : error.message);
  }
}

// Função para executar o script
async function main() {
  try {
    const title = 'Test Issue';
    const description = 'This is a test issue created by JavaScript Agent.';
    const projectKey = 'YOUR_PROJECT_KEY';

    await createIssue(title, description, projectKey);

    console.log('Script executed successfully.');
  } catch (error) {
    console.error('Error executing script:', error);
  }
}

// Executa o script se for CLI
if (require.main === module) {
  main();
}