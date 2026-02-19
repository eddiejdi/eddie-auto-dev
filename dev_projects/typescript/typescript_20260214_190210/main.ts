import { JiraClient } from 'jira-client';
import { Agent } from './agent';

class TypeScriptAgent extends Agent {
  constructor(jiraClient: JiraClient) {
    super(jiraClient);
  }

  async trackActivity(activity: string): Promise<void> {
    try {
      await this.jiraClient.createIssue({
        fields: {
          summary: `TypeScript Activity: ${activity}`,
          description: activity,
          project: { key: 'YOUR_PROJECT_KEY' },
          issuetype: { name: 'Task' }
        }
      });
      console.log('Activity tracked successfully');
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }
}

// Example usage
const jiraClient = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

const agent = new TypeScriptAgent(jiraClient);

(async () => {
  await agent.trackActivity('Implemented TypeScript Agent with Jira integration');
})();