import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraAgent implements Agent {
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
          summary: title,
          description: description
        }
      });
      console.log('Issue created successfully');
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async getIssues(): Promise<any[]> {
    try {
      const issues = await this.client.getIssues();
      return issues;
    } catch (error) {
      console.error('Error fetching issues:', error);
      return [];
    }
  }
}

// Example usage
const agent = new JiraAgent(
  'https://your-jira-instance.atlassian.net',
  'your-username',
  'your-password'
);

async function main() {
  try {
    await agent.createIssue('New Feature Request', 'Implement a new feature');
    const issues = await agent.getIssues();
    console.log('Issues:', issues);
  } catch (error) {
    console.error(error);
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}