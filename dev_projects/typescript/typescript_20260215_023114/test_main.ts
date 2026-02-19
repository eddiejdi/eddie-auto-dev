import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/types';
import { TypeScriptAgent } from './TypeScriptAgent';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'username', 'password');
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const title = 'TypeScript Agent Test';
      const description = 'This is a test issue created by the TypeScript Agent.';
      const issue = await agent.createIssue(title, description);
      expect(issue).toHaveProperty('key');
      expect(issue.fields.summary).toBe(title);
      expect(issue.fields.description).toBe(description);
    });

    it('should throw an error if the title or description is empty', async () => {
      await expect(agent.createIssue('', '')).rejects.toThrowError('Title and description cannot be empty');
    });
  });

  describe('updateIssue', () => {
    it('should update an issue with valid data', async () => {
      const issueId = 'ABC-123';
      const title = 'Updated Title';
      const description = 'Updated Description';
      const updatedIssue = await agent.updateIssue(issueId, title, description);
      expect(updatedIssue).toHaveProperty('key');
      expect(updatedIssue.fields.summary).toBe(title);
      expect(updatedIssue.fields.description).toBe(description);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const issueId = 'ABC-1234';
      await expect(agent.updateIssue(issueId, '', '')).rejects.toThrowError('Invalid issue key');
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue with valid data', async () => {
      const issueId = 'ABC-123';
      await agent.deleteIssue(issueId);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const issueId = 'ABC-1234';
      await expect(agent.deleteIssue(issueId)).rejects.toThrowError('Invalid issue key');
    });
  });
});