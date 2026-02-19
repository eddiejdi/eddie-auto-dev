import { JiraClient } from 'jira-client';

class TypeScriptAgent {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async trackActivity(activity: string): Promise<void> {
    try {
      await this.client.addCommentToIssue('YOUR_ISSUE_KEY', activity);
      console.log(`Activity tracked successfully for issue: YOUR_ISSUE_KEY`);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }

  async updateStatus(issueKey: string, status: string): Promise<void> {
    try {
      await this.client.updateIssueStatus(issueKey, status);
      console.log(`Status updated successfully for issue: ${issueKey}`);
    } catch (error) {
      console.error('Error updating status:', error);
    }
  }

  async closeIssue(issueKey: string): Promise<void> {
    try {
      await this.client.closeIssue(issueKey);
      console.log(`Issue closed successfully for issue: ${issueKey}`);
    } catch (error) {
      console.error('Error closing issue:', error);
    }
  }
}

// Example usage
const agent = new TypeScriptAgent(
  'https://your-jira-instance.atlassian.net',
  'your-username',
  'your-password'
);

(async () => {
  await agent.trackActivity('This is a test activity.');
  await agent.updateStatus('YOUR_ISSUE_KEY', 'In Progress');
  await agent.closeIssue('YOUR_ISSUE_KEY');
})();