import axios from 'axios';
import { Task } from './Task';

describe('JiraClient', () => {
  describe('createTask', () => {
    it('should create a task with valid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const newTask: Task = {
        id: null,
        title: 'Implement TypeScript Agent with Jira',
        description: 'Automate the registration of tasks and monitor activities.',
      };

      try {
        const createdTask = await taskManager.createTask(newTask);
        expect(createdTask).toEqual({
          id: expect.any(Number),
          title: newTask.title,
          description: newTask.description,
        });
      } catch (error) {
        throw new Error(`Failed to create task: ${error.message}`);
      }
    });

    it('should reject with an error when creating a task with invalid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const newTask: Task = {
        id: null,
        title: '',
        description: '',
      };

      try {
        await taskManager.createTask(newTask);
        expect.fail('Expected an error to be thrown');
      } catch (error) {
        expect(error.message).toContain('Failed to create task');
      }
    });
  });

  describe('getTasks', () => {
    it('should return a list of tasks with valid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const tasks: Task[] = [
        {
          id: 12345,
          title: 'Implement TypeScript Agent with Jira',
          description: 'Automate the registration of tasks and monitor activities.',
        },
        {
          id: 12346,
          title: 'Update TypeScript Agent with Jira',
          description: 'Automate the update of tasks and monitor activities.',
        },
      ];

      try {
        const retrievedTasks = await taskManager.getTasks();
        expect(retrievedTasks).toEqual(tasks);
      } catch (error) {
        throw new Error(`Failed to get tasks: ${error.message}`);
      }
    });

    it('should reject with an error when getting tasks', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);

      try {
        await taskManager.getTasks();
        expect.fail('Expected an error to be thrown');
      } catch (error) {
        expect(error.message).toContain('Failed to get tasks');
      }
    });
  });

  describe('updateTask', () => {
    it('should update a task with valid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const taskIdToUpdate = 12345;
      const updatedTask: Partial<Task> = {
        title: 'Update TypeScript Agent with Jira',
      };

      try {
        await taskManager.updateTask(taskIdToUpdate, updatedTask);
        // Add assertions to verify the update
      } catch (error) {
        throw new Error(`Failed to update task: ${error.message}`);
      }
    });

    it('should reject with an error when updating a task with invalid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const taskIdToUpdate = 12345;
      const updatedTask: Partial<Task> = {};

      try {
        await taskManager.updateTask(taskIdToUpdate, updatedTask);
        expect.fail('Expected an error to be thrown');
      } catch (error) {
        expect(error.message).toContain('Failed to update task');
      }
    });
  });

  describe('deleteTask', () => {
    it('should delete a task with valid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);
      const taskIdToDelete = 12345;

      try {
        await taskManager.deleteTask(taskIdToDelete);
        // Add assertions to verify the deletion
      } catch (error) {
        throw new Error(`Failed to delete task: ${error.message}`);
      }
    });

    it('should reject with an error when deleting a task with invalid data', async () => {
      const token = 'your-jira-token';
      const taskManager = new TaskManager(token);

      try {
        await taskManager.deleteTask(12345);
        expect.fail('Expected an error to be thrown');
      } catch (error) {
        expect(error.message).toContain('Failed to delete task');
      }
    });
  });
});