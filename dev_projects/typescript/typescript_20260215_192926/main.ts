import { JiraClient } from 'jira-client';

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async createIssue(title: string, description: string): Promise<void> {
    try {
      await this.jiraClient.createIssue({
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

  async updateIssue(issueId: string, title?: string, description?: string): Promise<void> {
    try {
      await this.jiraClient.updateIssue({
        fields: {
          summary: title,
          description: description
        },
        issueKey: issueId
      });
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueId: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue({
        issueKey: issueId
      });
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

// Example usage:
const agent = new TypeScriptAgent(
  'https://your-jira-instance.atlassian.net',
  'your-username',
  'your-password'
);

(async () => {
  await agent.createIssue('New Feature Request', 'Implement a new feature');
  await agent.updateIssue('NEW-123', 'Updated the feature description');
  await agent.deleteIssue('NEW-123');
})();