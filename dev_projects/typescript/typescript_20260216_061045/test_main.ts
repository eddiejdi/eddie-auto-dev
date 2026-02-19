import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';
    agent = new TypeScriptAgent(jiraUrl, username, password);
  });

  describe('logActivity', () => {
    it('should log an activity successfully', async () => {
      await agent.logActivity('New feature implemented');
      expect(console.log).to.have.been.calledWith('Activity logged successfully');
    });

    it('should throw an error if the activity is empty', async () => {
      await expect(agent.logActivity('')).rejects.to.throw('Error logging activity: Activity cannot be empty');
    });
  });

  describe('fetchActivities', () => {
    it('should fetch activities successfully', async () => {
      await agent.fetchActivities();
      expect(console.log).to.have.been.calledWith('Fetching activities...');
      expect(console.log).to.have.been.calledWith(`Summary: ${issue.fields.summary}`);
      expect(console.log).to.have.been.calledWith(`Description: ${issue.fields.description}`);
    });

    it('should throw an error if no issues are found', async () => {
      await agent.fetchActivities();
      expect(console.error).to.have.been.calledWith('No activities found');
    });
  });

  describe('closeActivity', () => {
    it('should close an activity successfully', async () => {
      await agent.closeActivity('YOUR_ISSUE_KEY');
      expect(console.log).to.have.been.calledWith(`Activity YOUR_ISSUE_KEY closed successfully`);
    });

    it('should throw an error if the issue key is invalid', async () => {
      await expect(agent.closeActivity('invalid-key')).rejects.to.throw('Error closing activity: Invalid issue key');
    });
  });
});