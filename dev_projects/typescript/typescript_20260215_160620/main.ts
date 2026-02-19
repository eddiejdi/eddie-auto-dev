import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      auth: { username, password },
    });
  }

  async createIssue(title: string, description: string): Promise<Issue> {
    const issueData = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' }, // Replace with your project key
        summary: title,
        description: description,
        issuetype: { name: 'Bug' },
      },
    };

    try {
      const createdIssue = await this.jiraClient.createIssue(issueData);
      console.log('Issue created:', createdIssue);
      return createdIssue;
    } catch (error) {
      console.error('Error creating issue:', error);
      throw error;
    }
  }

  async updateIssue(issueId: string, title?: string, description?: string): Promise<Issue> {
    const issueData = {};

    if (title) issueData.fields.summary = title;
    if (description) issueData.fields.description = description;

    try {
      const updatedIssue = await this.jiraClient.updateIssue(issueId, issueData);
      console.log('Issue updated:', updatedIssue);
      return updatedIssue;
    } catch (error) {
      console.error('Error updating issue:', error);
      throw error;
    }
  }

  async deleteIssue(issueId: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue(issueId);
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
    await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.');
    console.log('Integration created successfully');

    // Update the issue
    await agent.updateIssue('YOUR_ISSUE_ID', 'Updated title', 'Updated description');
    console.log('Issue updated successfully');

    // Delete the issue
    await agent.deleteIssue('YOUR_ISSUE_ID');
    console.log('Issue deleted successfully');
  } catch (error) {
    console.error('An error occurred:', error);
  }
}

if (require.main === module) {
  main();
}