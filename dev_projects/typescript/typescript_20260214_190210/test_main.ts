import { JiraClient } from 'jira-client';
import { Agent } from './agent';

describe('TypeScriptAgent', () => {
  let jiraClient: JiraClient;
  let agent: TypeScriptAgent;

  beforeEach(() => {
    jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });
    agent = new TypeScriptAgent(jiraClient);
  });

  describe('trackActivity', () => {
    it('should track an activity successfully with valid values', async () => {
      await agent.trackActivity('Implemented TypeScript Agent with Jira integration');
      expect(console.log).toHaveBeenCalledWith('Activity tracked successfully');
    });

    it('should throw an error when the activity is empty', async () => {
      await expect(agent.trackActivity('')).rejects.toThrowError(/Invalid activity/);
    });

    it('should throw an error when the activity contains invalid characters', async () => {
      await expect(agent.trackActivity('Invalid@#Activity')).rejects.toThrowError(/Invalid activity/);
    });
  });
});