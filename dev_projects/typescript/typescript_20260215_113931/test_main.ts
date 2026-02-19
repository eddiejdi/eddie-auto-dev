import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from './TypeScriptAgent';

describe('TypeScriptAgent', () => {
  let jiraClient: JiraClient;
  let agent: TypeScriptAgent;

  beforeEach(() => {
    // Configuração da conexão com Jira
    jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Cria uma instância do TypeScriptAgent
    agent = new TypeScriptAgent(jiraClient);
  });

  describe('startMonitoring', () => {
    it('should start monitoring activities successfully', async () => {
      await agent.startMonitoring();
      expect(agent.isMonitoring).toBe(true);
    });

    it('should throw an error if the Jira client is not configured correctly', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: ''
      });
      agent.jiraClient = jiraClient;
      await expect(agent.startMonitoring()).rejects.toThrow('Jira client is not configured correctly');
    });

    it('should throw an error if the Jira client is null', async () => {
      agent.jiraClient = null;
      await expect(agent.startMonitoring()).rejects.toThrow('Jira client is null');
    });
  });
});