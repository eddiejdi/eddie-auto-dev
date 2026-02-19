import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    agent = new TypeScriptAgent(
      'https://your-jira-instance.atlassian.net',
      'your-username',
      'your-password'
    );
  });

  describe('trackActivity', () => {
    it('should track activity successfully for an issue', async () => {
      const activity = 'This is a test activity.';
      await agent.trackActivity(activity);
      expect(console.log).to.have.been.calledWith(`Activity tracked successfully for issue: YOUR_ISSUE_KEY`);
    });

    it('should throw an error if the activity is empty', async () => {
      await expect(agent.trackActivity('')).to.rejectedWith('Error tracking activity:', 'Activity cannot be empty');
    });
  });

  describe('updateStatus', () => {
    it('should update status successfully for an issue', async () => {
      const issueKey = 'YOUR_ISSUE_KEY';
      const status = 'In Progress';
      await agent.updateStatus(issueKey, status);
      expect(console.log).to.have.been.calledWith(`Status updated successfully for issue: ${issueKey}`);
    });

    it('should throw an error if the issue key is empty', async () => {
      const status = 'In Progress';
      await expect(agent.updateStatus('', status)).to.rejectedWith('Error updating status:', 'Issue key cannot be empty');
    });
  });

  describe('closeIssue', () => {
    it('should close issue successfully for an issue', async () => {
      const issueKey = 'YOUR_ISSUE_KEY';
      await agent.closeIssue(issueKey);
      expect(console.log).to.have.been.calledWith(`Issue closed successfully for issue: ${issueKey}`);
    });

    it('should throw an error if the issue key is empty', async () => {
      await expect(agent.closeIssue('')).to.rejectedWith('Error closing issue:', 'Issue key cannot be empty');
    });
  });
});