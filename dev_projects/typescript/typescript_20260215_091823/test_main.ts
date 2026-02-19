import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/types';
import { TypeScriptAgentConfig } from './TypeScriptAgentConfig'; // Substitua com o caminho correto para o arquivo TypeScriptAgentConfig

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;
  let config: TypeScriptAgentConfig;

  beforeEach(() => {
    config = {
      jiraUrl: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    };
    agent = new TypeScriptAgent(config);
  });

  describe('startTracking', () => {
    it('should fetch issues and log them', async () => {
      const client = new JiraClient(config);
      const mockIssues = [
        { key: 'ABC123' },
        { key: 'XYZ456' }
      ];

      jest.spyOn(client, 'searchIssues').mockResolvedValue(mockIssues);

      await agent.startTracking();

      expect(console.log).toHaveBeenCalledWith(`Tracking issue ABC123`);
      expect(console.log).toHaveBeenCalledWith(`Tracking issue XYZ456`);
    });

    it('should handle errors during fetching issues', async () => {
      const client = new JiraClient(config);
      jest.spyOn(client, 'searchIssues').mockRejectedValue(new Error('Failed to fetch issues'));

      await agent.startTracking();

      expect(console.error).toHaveBeenCalledWith('Error tracking issues: Failed to fetch issues');
    });
  });

  describe('stopTracking', () => {
    it('should log a stop message', async () => {
      await agent.stopTracking();

      expect(console.log).toHaveBeenCalledWith('Stopped tracking issues');
    });

    it('should handle errors during stopping', async () => {
      jest.spyOn(agent, 'startTracking').mockRejectedValue(new Error('Failed to start tracking'));

      try {
        await agent.stopTracking();
      } catch (error) {
        expect(error.message).toBe('Failed to stop tracking issues');
      }
    });
  });
});