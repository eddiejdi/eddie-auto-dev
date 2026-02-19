import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/types';

interface IJiraAgent {
  logIssue: (issue: Issue) => void;
  trackActivity: (issueId: string, activity: string) => Promise<void>;
}

class TypeScriptAgent implements IJiraAgent {
  private jiraClient: JiraClient;

  constructor(jiraHost: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      host: jiraHost,
      auth: { username, password },
    });
  }

  logIssue(issue: Issue): void {
    console.log(`Logging issue: ${issue.key}`);
    // Implement logic to log the issue in a database or other system
  }

  async trackActivity(issueId: string, activity: string): Promise<void> {
    try {
      await this.jiraClient.issueService.update({
        issueKey: issueId,
        update: {
          fields: {
            description: `${activity} - ${new Date().toISOString()}`,
          },
        },
      });
      console.log(`Tracking activity for issue ${issueId}: ${activity}`);
    } catch (error) {
      console.error(`Error tracking activity for issue ${issueId}:`, error);
      throw new Error('Failed to track activity');
    }
  }

  async main(): Promise<void> {
    const jiraHost = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new TypeScriptAgent(jiraHost, username, password);

    try {
      const issueId = 'ABC-123';
      const activity = 'New feature implemented';

      await agent.logIssue({ key: issueId });
      await agent.trackActivity(issueId, activity);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }
}

if (require.main === module) {
  TypeScriptAgent.prototype.main();
}