import { JiraClient } from 'jira-client';
import { Agent } from './agent';

describe('TypeScriptAgent', () => {
  let jiraClient: JiraClient;
  let agent: Agent;

  beforeEach(() => {
    jiraClient = new JiraClient({
      serverUrl: 'https://your-jira-server.com',
      username: 'your-username',
      password: 'your-password',
    });

    agent = new Agent();
  });

  describe('startTracking', () => {
    it('should start the agent successfully', async () => {
      await tsAgent.startTracking();
      expect(console.log).toHaveBeenCalledWith('Agent started successfully');
    });
  });

  describe('stopTracking', () => {
    it('should stop the agent successfully', async () => {
      await tsAgent.stopTracking();
      expect(console.log).toHaveBeenCalledWith('Agent stopped successfully');
    });
  });

  describe('trackActivity', () => {
    it('should track an activity successfully', async () => {
      await tsAgent.trackActivity('New feature implemented');
      expect(console.log).toHaveBeenCalledWith(`Activity tracked successfully`);
    });

    it('should throw an error if the summary is invalid', async () => {
      try {
        await tsAgent.trackActivity('');
      } catch (error) {
        expect(error.message).toEqual('Summary cannot be empty');
      }
    });
  });

  describe('main', () => {
    it('should start, track an activity, and stop the agent successfully', async () => {
      await tsAgent.main();
      expect(console.log).toHaveBeenCalledWith('Agent started successfully');
      expect(console.log).toHaveBeenCalledWith(`Activity tracked successfully`);
      expect(console.log).toHaveBeenCalledWith('Agent stopped successfully');
    });
  });
});