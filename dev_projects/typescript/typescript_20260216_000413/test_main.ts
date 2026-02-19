import { IJiraAgent } from 'jira-client';
import { Issue } from 'jira-client/lib/types';
import { JiraClient } from 'jira-client';

describe('TypeScriptAgent', () => {
  describe('logIssue', () => {
    it('should log the issue with a valid key', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const issueKey = 'ABC-123';
      await agent.logIssue({ key: issueKey });
      expect(console.log).toHaveBeenCalledWith(`Logging issue: ${issueKey}`);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(agent.logIssue({ key: '' })).rejects.toThrowError('Invalid issue key');
    });
  });

  describe('trackActivity', () => {
    it('should track the activity for an existing issue with a valid description', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const issueId = 'ABC-123';
      const activity = 'New feature implemented';
      await agent.trackActivity(issueId, activity);
      expect(console.log).toHaveBeenCalledWith(`Tracking activity for issue ${issueId}: ${activity}`);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(agent.trackActivity('', 'New feature implemented')).rejects.toThrowError('Invalid issue key');
    });

    it('should throw an error if the activity is invalid', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(agent.trackActivity('ABC-123', '')).rejects.toThrowError('Invalid activity description');
    });
  });

  describe('main', () => {
    it('should log and track the activity for an existing issue with a valid description', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const issueId = 'ABC-123';
      const activity = 'New feature implemented';
      await agent.main();
      expect(console.log).toHaveBeenCalledWith(`Logging issue: ${issueId}`);
      expect(console.log).toHaveBeenCalledWith(`Tracking activity for issue ${issueId}: ${activity}`);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await expect(agent.main()).rejects.toThrowError('Invalid issue key');
    });
  });
});