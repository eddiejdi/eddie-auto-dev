import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraAgent {
  private client: JiraClient;

  constructor(token: string) {
    this.client = new JiraClient({
      auth: {
        username: 'your_username',
        password: token,
      },
      protocol: 'https',
      host: 'jira.yourdomain.com',
    });
  }

  async createIssue(title: string, description: string): Promise<void> {
    try {
      await this.client.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' },
        },
      });
      console.log('Issue created successfully');
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async updateIssue(issueKey: string, title?: string, description?: string): Promise<void> {
    try {
      await this.client.updateIssue({
        fields: {
          summary: title || '',
          description: description || '',
        },
        issueIdOrKey: issueKey,
      });
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueKey: string): Promise<void> {
    try {
      await this.client.deleteIssue({
        issueIdOrKey: issueKey,
      });
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

async function main() {
  const token = 'your_jira_token';
  const agent = new JiraAgent(token);

  await agent.createIssue('New Task', 'This is a new task for the project.');
  await agent.updateIssue('NEW-TASK-123', 'Updated task description.', 'Updated task summary.');
  await agent.deleteIssue('NEW-TASK-123');
}

if (require.main === module) {
  main();
}