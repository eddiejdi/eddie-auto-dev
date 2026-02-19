import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const title = 'TypeScript Agent Integration';
      const description = 'This is a test issue for the TypeScript Agent integration.';
      const createdIssue = await agent.createIssue(title, description);
      expect(createdIssue).toBeTruthy();
      expect(createdIssue.fields.summary).toBe(title);
      expect(createdIssue.fields.description).toBe(description);
    });

    it('should throw an error if the project key is invalid', async () => {
      try {
        await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.', { key: 'INVALID_PROJECT_KEY' });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid project key');
      }
    });

    it('should throw an error if the summary is invalid', async () => {
      try {
        await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.', { summary: '' });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Summary cannot be empty');
      }
    });

    it('should throw an error if the description is invalid', async () => {
      try {
        await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.', { description: '' });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Description cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const title = 'Updated Title';
      const description = 'Updated Description';
      await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.');
      const updatedIssue = await agent.updateIssue('YOUR_ISSUE_ID', title, description);
      expect(updatedIssue).toBeTruthy();
      expect(updatedIssue.fields.summary).toBe(title);
      expect(updatedIssue.fields.description).toBe(description);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.updateIssue('INVALID_ISSUE_ID', 'Updated Title', 'Updated Description');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid issue ID');
      }
    });

    it('should throw an error if the summary is invalid', async () => {
      try {
        await agent.updateIssue('YOUR_ISSUE_ID', '', 'Updated Description');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Summary cannot be empty');
      }
    });

    it('should throw an error if the description is invalid', async () => {
      try {
        await agent.updateIssue('YOUR_ISSUE_ID', 'Updated Title', '');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Description cannot be empty');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue with valid data', async () => {
      await agent.createIssue('TypeScript Agent Integration', 'This is a test issue for the TypeScript Agent integration.');
      await agent.deleteIssue('YOUR_ISSUE_ID');
      try {
        const deletedIssue = await agent.getIssue('YOUR_ISSUE_ID');
        expect(deletedIssue).toBeNull();
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Issue not found');
      }
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.deleteIssue('INVALID_ISSUE_ID');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(error.message).toContain('Invalid issue ID');
      }
    });
  });
});