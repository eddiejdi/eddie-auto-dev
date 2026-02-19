import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/types';

class TypeScriptAgent {
  private jira: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jira = new JiraClient({
      url: jiraUrl,
      auth: {
        username,
        password
      }
    });
  }

  async createIssue(title: string, description: string): Promise<Issue> {
    const issue = await this.jira.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    });
    return issue;
  }

  async updateIssue(issueId: string, title: string, description: string): Promise<Issue> {
    const updatedIssue = await this.jira.updateIssue({
      fields: {
        summary: title,
        description: description
      },
      issueKey: issueId
    });
    return updatedIssue;
  }

  async deleteIssue(issueId: string): Promise<void> {
    await this.jira.deleteIssue({ issueKey: issueId });
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new TypeScriptAgent(jiraUrl, username, password);

  try {
    const issue = await agent.createIssue('TypeScript Agent', 'This is a test issue for the TypeScript Agent.');
    console.log(`Created issue: ${issue.key}`);

    await agent.updateIssue(issue.key, 'Updated TypeScript Agent', 'This is an updated test issue for the TypeScript Agent.');
    console.log(`Updated issue: ${issue.key}`);

    await agent.deleteIssue(issue.key);
    console.log(`Deleted issue: ${issue.key}`);
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}