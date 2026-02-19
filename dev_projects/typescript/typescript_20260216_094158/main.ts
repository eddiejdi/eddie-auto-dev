import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/types';

// Define a classe para integrar TypeScript Agent com Jira
class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password,
    });
  }

  async createIssue(title: string, description: string): Promise<Issue> {
    try {
      const issueData = {
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' },
        },
      };

      const createdIssue = await this.jiraClient.createIssue(issueData);
      return createdIssue;
    } catch (error) {
      throw new Error(`Failed to create issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey: string, title?: string, description?: string): Promise<Issue> {
    try {
      const updateData = {};

      if (title) {
        updateData.fields.summary = title;
      }

      if (description) {
        updateData.fields.description = description;
      }

      const updatedIssue = await this.jiraClient.updateIssue(issueKey, updateData);
      return updatedIssue;
    } catch (error) {
      throw new Error(`Failed to update issue: ${error.message}`);
    }
  }

  async deleteIssue(issueKey: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue(issueKey);
    } catch (error) {
      throw new Error(`Failed to delete issue: ${error.message}`);
    }
  }
}

// Exemplo de uso
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new TypeScriptAgent(jiraUrl, username, password);

  try {
    const issue = await agent.createIssue('New Task', 'This is a new task.');
    console.log(`Created issue: ${issue.key}`);

    await agent.updateIssue(issue.key, 'Updated Task', 'This is an updated task.');
    console.log(`Updated issue: ${issue.key}`);

    await agent.deleteIssue(issue.key);
    console.log(`Deleted issue: ${issue.key}`);
  } catch (error) {
    console.error(error.message);
  }
}

if (require.main === module) {
  main();
}