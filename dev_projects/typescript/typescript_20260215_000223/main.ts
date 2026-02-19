import { JiraClient } from 'jira-client';
import { Agent } from './agent';

class TypeScriptAgent extends Agent {
  constructor(private jiraClient: JiraClient) {
    super(jiraClient);
  }

  async trackActivity(issueKey: string, activityDescription: string): Promise<void> {
    try {
      await this.jiraClient.issue.update({
        issueKey,
        update: {
          fields: {
            description: `${activityDescription}\n\n${this.getTimestamp()}`,
          },
        },
      });
      console.log(`Activity logged for issue ${issueKey}`);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }

  private getTimestamp(): string {
    const now = new Date();
    return `${now.toLocaleDateString()} - ${now.toLocaleTimeString()}`;
  }
}

// Example usage
async function main() {
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net',
    username: 'your-username',
    password: 'your-password',
  });

  const agent = new TypeScriptAgent(jiraClient);

  await agent.trackActivity('ABC-123', 'This is a test activity');
}

if (require.main === module) {
  main();
}