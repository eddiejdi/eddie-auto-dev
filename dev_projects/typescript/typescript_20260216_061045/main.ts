import { JiraClient } from 'jira-client';

class TypeScriptAgent {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async logActivity(activity: string): Promise<void> {
    try {
      await this.client.createIssue({
        fields: {
          summary: activity,
          description: 'Log of activity',
          project: {
            key: 'YOUR_PROJECT_KEY'
          }
        }
      });
      console.log('Activity logged successfully');
    } catch (error) {
      console.error('Error logging activity:', error);
    }
  }

  async fetchActivities(): Promise<void> {
    try {
      const issues = await this.client.search({
        jql: 'project = YOUR_PROJECT_KEY',
        fields: ['summary', 'description']
      });
      if (issues.total > 0) {
        console.log('Fetching activities...');
        for (const issue of issues.issues) {
          console.log(`Summary: ${issue.fields.summary}`);
          console.log(`Description: ${issue.fields.description}`);
        }
      } else {
        console.log('No activities found');
      }
    } catch (error) {
      console.error('Error fetching activities:', error);
    }
  }

  async closeActivity(issueKey: string): Promise<void> {
    try {
      await this.client.updateIssue({
        issueKey,
        fields: {
          status: {
            name: 'Closed'
          }
        }
      });
      console.log(`Activity ${issueKey} closed successfully`);
    } catch (error) {
      console.error('Error closing activity:', error);
    }
  }

  async main(): Promise<void> {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const agent = new TypeScriptAgent(jiraUrl, username, password);

    await agent.logActivity('New feature implemented');
    await agent.fetchActivities();
    await agent.closeActivity('YOUR_ISSUE_KEY');
  }
}

if (require.main === module) {
  TypeScriptAgent.main().catch(error => console.error('Error:', error));
}