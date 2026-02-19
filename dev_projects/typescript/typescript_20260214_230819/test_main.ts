import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

interface TypeScriptAgent {
  connect: () => Promise<void>;
  trackIssue: (issueId: string) => Promise<void>;
}

class TypeScriptAgentImpl implements TypeScriptAgent {
  private client: JiraClient;

  constructor(url: string, username: string, password: string) {
    this.client = new JiraClient({
      url,
      username,
      password,
    });
  }

  async connect(): Promise<void> {
    try {
      await this.client.login();
      console.log('Connected to Jira');
    } catch (error) {
      throw new Error(`Failed to connect to Jira: ${error}`);
    }
  }

  async trackIssue(issueId: string): Promise<void> {
    try {
      const issue = await this.client.getIssue(issueId);
      console.log(`Tracking issue ${issue.key}: ${issue.fields.summary}`);
    } catch (error) {
      throw new Error(`Failed to track issue ${issueId}: ${error}`);
    }
  }
}

// Example usage
async function main() {
  try {
    const agent = new TypeScriptAgentImpl('https://your-jira-instance.atlassian.net', 'username', 'password');
    await agent.connect();
    await agent.trackIssue('ABC-123');
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