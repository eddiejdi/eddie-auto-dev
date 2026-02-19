import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('JiraAgent', () => {
  let agent: JiraAgent;

  beforeEach(() => {
    const token = 'your_jira_token';
    agent = new JiraAgent(token);
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      await agent.createIssue('New Task', 'This is a new task for the project.');
      expect(console.log).toHaveBeenCalledWith('Issue created successfully');
    });

    it('should throw an error if the title is empty', async () => {
      try {
        await agent.createIssue('', 'This is a new task for the project.');
      } catch (error) {
        expect(error.message).toBe('Title cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue with valid data', async () => {
      await agent.createIssue('New Task', 'This is a new task for the project.');
      await agent.updateIssue('NEW-TASK-123', 'Updated task description.', 'Updated task summary.');
      expect(console.log).toHaveBeenCalledWith('Issue updated successfully');
    });

    it('should throw an error if the issue key is empty', async () => {
      try {
        await agent.updateIssue('', 'Updated task description.', 'Updated task summary.');
      } catch (error) {
        expect(error.message).toBe('Issue key cannot be empty');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue with valid data', async () => {
      await agent.createIssue('New Task', 'This is a new task for the project.');
      await agent.deleteIssue('NEW-TASK-123');
      expect(console.log).toHaveBeenCalledWith('Issue deleted successfully');
    });

    it('should throw an error if the issue key is empty', async () => {
      try {
        await agent.deleteIssue('');
      } catch (error) {
        expect(error.message).toBe('Issue key cannot be empty');
      }
    });
  });
});