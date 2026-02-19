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

  async updateIssue(issueKey: string, title?: string, description?: string): Promise<void> {
    try {
      await this.jiraClient.updateIssue({
        fields: {
          summary: title,
          description: description
        },
        id: issueKey
      });

      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueKey: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue({
        id: issueKey
      });

      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new TypeScriptAgent(jiraUrl, username, password);

  try {
    await agent.createIssue('New Feature Request', 'Implement a new feature in the application');
    await agent.updateIssue('NEW_FEATURE_REQUEST_123', 'Add user authentication to the application', 'Fix login page issues');
    await agent.deleteIssue('NEW_FEATURE_REQUEST_123');
  } catch (error) {
    console.error('Error executing Jira operations:', error);
  }
}

if (require.main === module) {
  main();
}