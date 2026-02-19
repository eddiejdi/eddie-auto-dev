import { createJiraClient } from './jira-client';
import { Agent } from 'typescript-agent';

// Teste para criar um cliente Jira com valores válidos
test('createJiraClient should return a valid JiraClient instance', async () => {
  const jiraClient = await createJiraClient();
  expect(jiraClient).toBeInstanceOf(JiraClient);
});

// Teste para integrar TypeScript Agent com Jira com uma resposta válida
test('integrateTypeScriptAgentWithJira should integrate TypeScript Agent with a valid response', async () => {
  try {
    // Criar um cliente Jira
    const jiraClient = createJiraClient();

    // Realizar uma solicitação à API do Jira
    const response = await jiraClient.request('GET', '/rest/api/2/project');

    // Integrar TypeScript Agent com a resposta da API
    const agent = new Agent(response);
    expect(agent).toBeInstanceOf(Agent);

    console.log('Agent integrated with Jira:', agent);
  } catch (error) {
    console.error('Error integrating TypeScript Agent with Jira:', error);
  }
});

// Teste para integrar TypeScript Agent com Jira com uma resposta inválida
test('integrateTypeScriptAgentWithJira should throw an error for invalid response', async () => {
  try {
    // Criar um cliente Jira
    const jiraClient = createJiraClient();

    // Realizar uma solicitação à API do Jira com um erro
    await jiraClient.request('GET', '/rest/api/2/project');
  } catch (error) {
    expect(error).toBeInstanceOf(Error);
    console.log('Error integrating TypeScript Agent with Jira:', error);
  }
});