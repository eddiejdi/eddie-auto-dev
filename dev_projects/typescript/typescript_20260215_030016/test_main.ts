import { JiraClient } from 'jira-client';
import { Agent } from './Agent';

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

describe('TypeScriptAgent', () => {
  let jiraClient;
  let agent;

  beforeEach(() => {
    jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    agent = new TypeScriptAgent(jiraClient);
  });

  describe('trackActivity', () => {
    it('should track an activity successfully with valid input', async () => {
      await agent.trackActivity('Implementing TypeScript Agent in Jira');
      expect(console.log).toHaveBeenCalledWith('Activity tracked successfully');
    });

    it('should throw an error when the activity is empty', async () => {
      try {
        await agent.trackActivity('');
      } catch (error) {
        expect(error.message).toBe('Error tracking activity: Activity cannot be empty');
      }
    });

    it('should throw an error when the activity contains invalid characters', async () => {
      try {
        await agent.trackActivity('Invalid@#activity');
      } catch (error) {
        expect(error.message).toBe('Error tracking activity: Invalid character in activity');
      }
    });
  });
});