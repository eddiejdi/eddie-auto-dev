const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

// Função para configurar o JavaScript Agent em Jira
async function configureJavaScriptAgent(jiraToken, jiraUrl) {
  const client = new JiraClient({
    auth: {
      username: 'your_username',
      password: 'your_password'
    },
    baseUrl: jiraUrl,
    headers: {
      'Authorization': `Basic ${Buffer.from(`${jiraToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`
    }
  });

  const config = {
    name: 'JavaScript Agent',
    description: 'Tracks JavaScript activities in Jira',
    url: 'https://your_javascript_agent_url'
  };

  try {
    await client.configuration.create(config);
    console.log('JavaScript Agent configured successfully');
  } catch (error) {
    console.error('Error configuring JavaScript Agent:', error);
  }
}

// Função para registrar um evento no Jira
async function registerEvent(jiraToken, jiraUrl, issueKey, eventType, eventData) {
  const client = new JiraClient({
    auth: {
      username: 'your_username',
      password: 'your_password'
    },
    baseUrl: jiraUrl,
    headers: {
      'Authorization': `Basic ${Buffer.from(`${jiraToken}:${process.env.JIRA_API_TOKEN}`).toString('base64')}`
    }
  });

  const event = {
    issueKey: issueKey,
    eventType: eventType,
    eventData: eventData
  };

  try {
    await client.event.create(event);
    console.log(`Event registered successfully for issue ${issueKey}`);
  } catch (error) {
    console.error('Error registering event:', error);
  }
}

// Função main para executar o script
async function main() {
  const jiraToken = process.env.JIRA_API_TOKEN;
  const jiraUrl = 'https://your_jira_url';
  const issueKey = 'YOUR-ISSUE-KEY';
  const eventType = 'JavaScript Activity';
  const eventData = { message: 'This is a JavaScript activity event' };

  await configureJavaScriptAgent(jiraToken, jiraUrl);
  await registerEvent(jiraToken, jiraUrl, issueKey, eventType, eventData);
}

// Verifica se o script é executado como um módulo
if (require.main === module) {
  main();
}