const axios = require('axios');
const { promisify } = require('util');

// Função para criar uma requisição HTTP usando Axios
async function makeRequest(url) {
  try {
    const response = await axios.get(url);
    return response.data;
  } catch (error) {
    throw new Error(`Failed to fetch data from ${url}: ${error.message}`);
  }
}

// Função para enviar um log para Jira
async function sendLogToJira(logData) {
  try {
    const url = 'https://your-jira-instance.atlassian.net/rest/api/3/log';
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Basic ${Buffer.from('your-api-key:your-api-secret').toString('base64')}`
    };
    await makeRequest(url, JSON.stringify(logData), headers);
    console.log('Log sent to Jira successfully');
  } catch (error) {
    throw new Error(`Failed to send log to Jira: ${error.message}`);
  }
}

// Função para monitorar atividades em JavaScript
async function monitorJavaScriptActivity() {
  try {
    const logs = await makeRequest('https://your-api-endpoint.com/logs');
    for (const log of logs) {
      console.log(`Log received: ${log}`);
      await sendLogToJira(log);
    }
  } catch (error) {
    throw new Error(`Failed to monitor JavaScript activity: ${error.message}`);
  }
}

// Função principal
async function main() {
  try {
    await monitorJavaScriptActivity();
  } catch (error) {
    console.error('An error occurred:', error.message);
  }
}

if (require.main === module) {
  main().catch(error => {
    console.error('Error in main:', error.message);
  });
}