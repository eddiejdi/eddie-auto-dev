import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

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
        issueIdOrKey: issueKey
      });
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueKey: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue({
        issueIdOrKey: issueKey
      });
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }

  async getIssues(query: string): Promise<any[]> {
    try {
      const issues = await this.jiraClient.searchForIssues(query);
      return issues;
    } catch (error) {
      console.error('Error fetching issues:', error);
      return [];
    }
  }
}

async function main() {
  const agent = new TypeScriptAgent(
    'https://your-jira-instance.atlassian.net',
    'your-username',
    'your-password'
  );

  try {
    await agent.createIssue('My New Issue', 'This is a test issue.');
    await agent.updateIssue('YOUR_ISSUE_KEY', 'Updated Title', 'Updated Description');
    await agent.deleteIssue('YOUR_ISSUE_KEY');
    const issues = await agent.getIssues('project=YOUR_PROJECT_KEY');
    console.log('Fetched Issues:', issues);
  } catch (error) {
    console.error('Main function failed:', error);
  }
}

if (require.main === module) {
  main();
}