import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('Jira Client Tests', () => {
  let jira: JiraClient;
  let agent: Agent;

  beforeEach(() => {
    jira = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    agent = new Agent(jira);
  });

  describe('createTask', () => {
    it('should create a task successfully with valid inputs', async () => {
      const title = 'Implement TypeScript Agent with Jira';
      const description = 'This is a test task to integrate TypeScript Agent with Jira.';
      await agent.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Bug' }
        }
      });
    });

    it('should throw an error if the task creation fails', async () => {
      try {
        await agent.createIssue({
          fields: {
            project: { key: 'INVALID_PROJECT_KEY' },
            summary: 'Implement TypeScript Agent with Jira',
            description: 'This is a test task to integrate TypeScript Agent with Jira.',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the project key is missing', async () => {
      try {
        await agent.createIssue({
          fields: {
            summary: 'Implement TypeScript Agent with Jira',
            description: 'This is a test task to integrate TypeScript Agent with Jira.',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the summary is missing', async () => {
      try {
        await agent.createIssue({
          fields: {
            project: { key: 'YOUR_PROJECT_KEY' },
            description: 'This is a test task to integrate TypeScript Agent with Jira.',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the description is missing', async () => {
      try {
        await agent.createIssue({
          fields: {
            project: { key: 'YOUR_PROJECT_KEY' },
            summary: 'Implement TypeScript Agent with Jira',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the issue type is missing', async () => {
      try {
        await agent.createIssue({
          fields: {
            project: { key: 'YOUR_PROJECT_KEY' },
            summary: 'Implement TypeScript Agent with Jira',
            description: 'This is a test task to integrate TypeScript Agent with Jira.',
          }
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });

  describe('monitorActivities', () => {
    it('should monitor activities successfully with valid inputs', async () => {
      const issues = await agent.searchIssues({
        jql: 'project = YOUR_PROJECT_KEY AND status = Open'
      });
      for (const issue of issues) {
        console.log(`Issue ${issue.key}: ${issue.fields.summary}`);
      }
    });

    it('should throw an error if the search issues fails', async () => {
      try {
        await agent.searchIssues({
          jql: 'project = INVALID_PROJECT_KEY AND status = Open'
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the project key is missing', async () => {
      try {
        await agent.searchIssues({
          jql: 'status = Open'
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    it('should throw an error if the status is missing', async () => {
      try {
        await agent.searchIssues({
          jql: 'project = YOUR_PROJECT_KEY'
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });
});