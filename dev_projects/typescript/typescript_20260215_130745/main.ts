import { JiraClient } from 'jira-client';
import { Agent } from './agent';

class TypeScriptAgent {
  private jiraClient: JiraClient;
  private agent: Agent;

  constructor(jiraClient: JiraClient, agent: Agent) {
    this.jiraClient = jiraClient;
    this.agent = agent;
  }

  async startTracking() {
    try {
      await this.agent.start();
      console.log('Agent started successfully');
    } catch (error) {
      console.error('Failed to start agent:', error);
    }
  }

  async stopTracking() {
    try {
      await this.agent.stop();
      console.log('Agent stopped successfully');
    } catch (error) {
      console.error('Failed to stop agent:', error);
    }
  }

  async trackActivity(activity: string) {
    try {
      await this.jiraClient.createIssue({
        fields: {
          summary: `Activity: ${activity}`,
          description: `Description of the activity`,
        },
      });
      console.log(`Activity tracked successfully`);
    } catch (error) {
      console.error('Failed to track activity:', error);
    }
  }

  async main() {
    const jiraClient = new JiraClient({
      serverUrl: 'https://your-jira-server.com',
      username: 'your-username',
      password: 'your-password',
    });

    const agent = new Agent();

    await this.startTracking();
    await this.trackActivity('New feature implemented');
    await this.stopTracking();
  }
}

// Example usage
const jiraClient = new JiraClient({
  serverUrl: 'https://your-jira-server.com',
  username: 'your-username',
  password: 'your-password',
});

const agent = new Agent();

const tsAgent = new TypeScriptAgent(jiraClient, agent);
tsAgent.main();