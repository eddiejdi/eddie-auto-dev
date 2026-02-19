import { JiraClient } from 'jira-client';
import { createLogger, format, transports } from 'winston';

const logger = createLogger({
  level: 'info',
  format: format.combine(
    format.timestamp(),
    format.json()
  ),
  transports: [
    new transports.Console({ level: 'info' })
  ]
});

class JiraService {
  private client: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async createIssue(issueData: any): Promise<any> {
    try {
      const issue = await this.client.createIssue(issueData);
      logger.info(`Issue created successfully: ${issue.key}`);
      return issue;
    } catch (error) {
      logger.error(`Error creating issue: ${error.message}`);
      throw error;
    }
  }

  async updateIssue(issueKey: string, issueData: any): Promise<any> {
    try {
      const issue = await this.client.updateIssue(issueKey, issueData);
      logger.info(`Issue updated successfully: ${issue.key}`);
      return issue;
    } catch (error) {
      logger.error(`Error updating issue: ${error.message}`);
      throw error;
    }
  }

  async deleteIssue(issueKey: string): Promise<any> {
    try {
      const issue = await this.client.deleteIssue(issueKey);
      logger.info(`Issue deleted successfully: ${issue.key}`);
      return issue;
    } catch (error) {
      logger.error(`Error deleting issue: ${error.message}`);
      throw error;
    }
  }

  async getIssue(issueKey: string): Promise<any> {
    try {
      const issue = await this.client.getIssue(issueKey);
      logger.info(`Issue retrieved successfully: ${issue.key}`);
      return issue;
    } catch (error) {
      logger.error(`Error retrieving issue: ${error.message}`);
      throw error;
    }
  }

  async searchIssues(query: string): Promise<any[]> {
    try {
      const issues = await this.client.searchIssues(query);
      logger.info(`Issues searched successfully: ${issues.length}`);
      return issues;
    } catch (error) {
      logger.error(`Error searching issues: ${error.message}`);
      throw error;
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const jiraService = new JiraService(jiraUrl, username, password);

  try {
    // Create an issue
    const issueData = {
      project: { key: 'YOUR_PROJECT_KEY' },
      summary: 'Test Issue',
      description: 'This is a test issue created using TypeScript and Jira Client.',
      issuetype: { name: 'Bug' }
    };
    await jiraService.createIssue(issueData);

    // Update an existing issue
    const issueKey = 'YOUR_ISSUE_KEY';
    const updatedIssueData = {
      summary: 'Updated Test Issue'
    };
    await jiraService.updateIssue(issueKey, updatedIssueData);

    // Delete an issue
    await jiraService.deleteIssue(issueKey);

    // Get an issue
    const retrievedIssue = await jiraService.getIssue(issueKey);
    logger.info(`Retrieved issue: ${JSON.stringify(retrievedIssue)}`);

    // Search issues
    const query = 'summary~"Test Issue"';
    const issues = await jiraService.searchIssues(query);
    logger.info(`Search results: ${issues.length}`);
  } catch (error) {
    logger.error('An error occurred:', error.message);
  }
}

if (require.main === module) {
  main();
}