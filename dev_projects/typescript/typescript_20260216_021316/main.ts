import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/types';

class TypeScriptAgent {
  private jira: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jira = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async createIssue(title: string, description: string): Promise<Issue> {
    try {
      const issueData: Issue = {
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Bug' }
        }
      };

      const createdIssue = await this.jira.createIssue(issueData);
      return createdIssue;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(id: string, title?: string, description?: string): Promise<Issue> {
    try {
      const updatedFields: Partial<Issue.Fields> = {};

      if (title) {
        updatedFields.summary = title;
      }

      if (description) {
        updatedFields.description = description;
      }

      const issueData: Issue = {
        fields: updatedFields
      };

      const updatedIssue = await this.jira.updateIssue(id, issueData);
      return updatedIssue;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(id: string): Promise<void> {
    try {
      await this.jira.deleteIssue(id);
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

// Example usage
const agent = new TypeScriptAgent(
  'https://your-jira-instance.atlassian.net',
  'your-username',
  'your-password'
);

(async () => {
  try {
    const createdIssue = await agent.createIssue('Bug in TypeScript', 'This is a test bug.');
    console.log('Created issue:', createdIssue);

    const updatedIssue = await agent.updateIssue(createdIssue.id, 'Updated title', 'Updated description');
    console.log('Updated issue:', updatedIssue);

    await agent.deleteIssue(createdIssue.id);
    console.log('Deleted issue successfully.');
  } catch (error) {
    console.error(error);
  }
})();