import { JiraClient } from 'jira-client';
import { Agent } from './agent';

describe('TypeScriptAgentJira', () => {
  let jiraClient: JiraClient;
  let agent: Agent;
  let tsAgentJira: TypeScriptAgentJira;

  beforeEach(() => {
    jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    agent = new Agent();

    tsAgentJira = new TypeScriptAgentJira(jiraClient, agent);
  });

  describe('startTracking', () => {
    it('should start tracking successfully with valid parameters', async () => {
      await tsAgentJira.startTracking();
      expect(console.log).toHaveBeenCalledWith('Tracking started successfully');
    });

    it('should throw an error if the Jira client is null', async () => {
      tsAgentJira.jiraClient = null;
      await expect(tsAgentJira.startTracking()).rejects.toThrowError('Jira client cannot be null');
    });
  });

  describe('stopTracking', () => {
    it('should stop tracking successfully with valid parameters', async () => {
      await tsAgentJira.stopTracking();
      expect(console.log).toHaveBeenCalledWith('Tracking stopped successfully');
    });

    it('should throw an error if the Jira client is null', async () => {
      tsAgentJira.jiraClient = null;
      await expect(tsAgentJira.stopTracking()).rejects.toThrowError('Jira client cannot be null');
    });
  });
});