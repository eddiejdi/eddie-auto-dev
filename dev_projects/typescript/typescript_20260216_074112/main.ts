import { JiraClient } from 'jira-client';
import { createLogger } from 'winston';

const logger = createLogger({
  level: 'info',
  format: {
    json: true,
  },
});

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraHost: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      host: jiraHost,
      username: username,
      password: password,
    });
  }

  async trackActivity(issueKey: string, activityDescription: string): Promise<void> {
    try {
      await this.jiraClient.issue.addComment({
        issueIdOrKey: issueKey,
        body: activityDescription,
      });

      logger.info(`Activity tracked for issue ${issueKey}`);
    } catch (error) {
      logger.error(`Error tracking activity for issue ${issueKey}:`, error);
    }
  }

  async closeIssue(issueKey: string, comment?: string): Promise<void> {
    try {
      await this.jiraClient.issue.update({
        issueIdOrKey: issueKey,
        fields: {
          status: {
            name: 'Closed',
          },
        },
      });

      if (comment) {
        await this.trackActivity(issueKey, comment);
      }

      logger.info(`Issue ${issueKey} closed`);
    } catch (error) {
      logger.error(`Error closing issue ${issueKey}:`, error);
    }
  }
}

async function main() {
  const jiraHost = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new TypeScriptAgent(jiraHost, username, password);

  try {
    await agent.trackActivity('ABC-123', 'This is a test activity');
    await agent.closeIssue('ABC-123', 'This issue was resolved');
  } catch (error) {
    logger.error(`Main function failed:`, error);
  }
}

if (require.main === module) {
  main();
}