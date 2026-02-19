import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/types';

class TypeScriptAgent {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async createIssue(title: string, description: string): Promise<Issue> {
    try {
      const issue = await this.client.createIssue({
        fields: {
          summary: title,
          description: description,
          project: { key: 'YOUR_PROJECT_KEY' },
          issuetype: { name: 'Bug' }
        }
      });
      return issue;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(issueId: string, title?: string, description?: string): Promise<Issue> {
    try {
      const updatedFields = {};
      if (title) updatedFields.summary = title;
      if (description) updatedFields.description = description;

      const issue = await this.client.updateIssue({
        issueKey: issueId,
        fields: updatedFields
      });
      return issue;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueId: string): Promise<void> {
    try {
      await this.client.deleteIssue({
        issueKey: issueId
      });
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

// Usage example:
(async () => {
  const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'username', 'password');
  
  try {
    const issue = await agent.createIssue('TypeScript Agent Test', 'This is a test issue created by the TypeScript Agent.');
    console.log('Created issue:', issue);

    // Update the issue
    await agent.updateIssue(issue.key, 'Updated Title', 'Updated Description');

    // Delete the issue
    await agent.deleteIssue(issue.key);
    console.log('Deleted issue');
  } catch (error) {
    console.error('Error executing operations:', error);
  }
})();