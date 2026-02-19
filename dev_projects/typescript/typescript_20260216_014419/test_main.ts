import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from './TypeScriptAgent';

describe('TaskTracker', () => {
  let taskTracker: TaskTracker;

  beforeEach(() => {
    taskTracker = new TaskTracker();
  });

  describe('addTask', () => {
    it('should add a task with valid title and description', async () => {
      await taskTracker.addTask('Fix bug in code', 'Update the bug fix to ensure it works correctly');
      expect(taskTracker.getTasks()).toContain({ title: 'Fix bug in code', description: 'Update the bug fix to ensure it works correctly' });
    });

    it('should throw an error if title is empty', async () => {
      await expect(() => taskTracker.addTask('', 'Update the bug fix to ensure it works correctly')).rejects.toThrowError('Title cannot be empty');
    });

    it('should throw an error if description is empty', async () => {
      await expect(() => taskTracker.addTask('Fix bug in code', '')).rejects.toThrowError('Description cannot be empty');
    });
  });

  describe('updateTask', () => {
    it('should update a task with valid id, title, and description', async () => {
      await taskTracker.addTask('Fix bug in code', 'Update the bug fix to ensure it works correctly');
      await taskTracker.updateTask(1, 'Fix bug in code', 'Corrected the bug in the code');
      expect(taskTracker.getTasks()).toContain({ id: 1, title: 'Fix bug in code', description: 'Corrected the bug in the code' });
    });

    it('should throw an error if task is not found', async () => {
      await expect(() => taskTracker.updateTask(2, 'Fix bug in code', 'Corrected the bug in the code')).rejects.toThrowError('Task not found');
    });

    it('should throw an error if title is empty', async () => {
      await expect(() => taskTracker.updateTask(1, '', 'Corrected the bug in the code')).rejects.toThrowError('Title cannot be empty');
    });

    it('should throw an error if description is empty', async () => {
      await expect(() => taskTracker.updateTask(1, 'Fix bug in code', '')).rejects.toThrowError('Description cannot be empty');
    });
  });

  describe('deleteTask', () => {
    it('should delete a task with valid id', async () => {
      await taskTracker.addTask('Fix bug in code', 'Update the bug fix to ensure it works correctly');
      await taskTracker.deleteTask(1);
      expect(taskTracker.getTasks()).not.toContain({ id: 1, title: 'Fix bug in code', description: 'Update the bug fix to ensure it works correctly' });
    });

    it('should throw an error if task is not found', async () => {
      await expect(() => taskTracker.deleteTask(2)).rejects.toThrowError('Task not found');
    });
  });

  describe('run', () => {
    it('should run tasks and log them to console', async () => {
      await taskTracker.addTask('Fix bug in code', 'Update the bug fix to ensure it works correctly');
      await taskTracker.run();
      expect(console.log).toHaveBeenCalledWith('- Fix bug in code: Update the bug fix to ensure it works correctly');
    });
  });
});