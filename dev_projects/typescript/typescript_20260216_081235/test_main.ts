import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

// Define a class to represent an issue in Jira
class Issue {
  private id: string;
  private summary: string;
  private status: string;

  constructor(id: string, summary: string, status: string) {
    this.id = id;
    this.summary = summary;
    this.status = status;
  }

  getId(): string {
    return this.id;
  }

  getSummary(): string {
    return this.summary;
  }

  getStatus(): string {
    return this.status;
  }
}

// Define a class to represent the TypeScript Agent
class TypeScriptAgent {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password,
    });
  }

  async createIssue(issue: Issue): Promise<void> {
    try {
      await this.client.createIssue(issue);
      console.log(`Issue ${issue.getId()} created successfully.`);
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async updateIssue(issue: Issue): Promise<void> {
    try {
      await this.client.updateIssue(issue);
      console.log(`Issue ${issue.getId()} updated successfully.`);
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }
}

// Example usage
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new TypeScriptAgent(jiraUrl, username, password);

  const issue = new Issue('101', 'New feature request', 'In Progress');

  await agent.createIssue(issue);
}

if (require.main === module) {
  main();
}