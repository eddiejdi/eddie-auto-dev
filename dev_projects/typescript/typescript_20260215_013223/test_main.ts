import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    agent = new TypeScriptAgent(
      'https://your-jira-instance.atlassian.net',
      'your-username',
      'your-password'
    );
  });

  describe('createIssue', () => {
    it('should create an issue with valid fields', async () => {
      const title = 'My New Issue';
      const description = 'This is a test issue.';
      await agent.createIssue(title, description);
      expect(console.log).toHaveBeenCalledWith('Issue created successfully');
    });

    it('should throw an error if the title is empty', async () => {
      try {
        await agent.createIssue('', 'This is a test issue.');
      } catch (error) {
        expect(error.message).toBe('Title cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid fields', async () => {
      const title = 'Updated Title';
      const description = 'Updated Description';
      await agent.updateIssue('YOUR_ISSUE_KEY', title, description);
      expect(console.log).toHaveBeenCalledWith('Issue updated successfully');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await agent.updateIssue('INVALID_KEY', 'Updated Title', 'Updated Description');
      } catch (error) {
        expect(error.message).toBe('Invalid issue key');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue', async () => {
      await agent.deleteIssue('YOUR_ISSUE_KEY');
      expect(console.log).toHaveBeenCalledWith('Issue deleted successfully');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await agent.deleteIssue('INVALID_KEY');
      } catch (error) {
        expect(error.message).toBe('Invalid issue key');
      }
    });
  });

  describe('getIssues', () => {
    it('should fetch issues with a valid query', async () => {
      const issues = await agent.getIssues('project=YOUR_PROJECT_KEY');
      console.log('Fetched Issues:', issues);
    });

    it('should throw an error if the query is invalid', async () => {
      try {
        await agent.getIssues('');
      } catch (error) {
        expect(error.message).toBe('Invalid query');
      }
    });
  });
});