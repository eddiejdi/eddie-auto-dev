import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraAgent {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      auth: {
        username,
        password
      }
    });
  }

  async createIssue(title: string, description: string): Promise<void> {
    try {
      await this.client.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description
        }
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
          summary: title,
          description: description
        },
        issueIdOrKey: issueKey
      });
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueKey: string): Promise<void> {
    try {
      await this.client.deleteIssue({
        issueIdOrKey: issueKey
      });
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

// Example usage
(async () => {
  const agent = new JiraAgent('https://your-jira-instance.com', 'username', 'password');

  try {
    await agent.createIssue('New Task', 'This is a new task for the project');
    await agent.updateIssue('NEW-TASK-123', 'Updated task description');
    await agent.deleteIssue('NEW-TASK-123');
  } catch (error) {
    console.error(error);
  }
})();