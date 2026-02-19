import { expect } from 'chai';
import { Task, Project, User, JiraIntegrator, TypeSystem } from './your-file-name';

describe('JiraIntegrator', () => {
  describe('getProjectIssues', () => {
    it('should return an array of tasks for a given project key', async () => {
      const mockJiraClient = {
        searchJql: jest.fn().mockResolvedValue([{ id: '123' }, { id: '456' }]),
      };
      const integrator = new JiraIntegrator('your-jira-token', 'https://your-jira-instance.atlassian.net');
      const tasks = await integrator.getProjectIssues('YOUR-PROJECT-KEY');
      expect(tasks).to.have.lengthOf(2);
    });

    it('should throw an error if the project key is invalid', async () => {
      const mockJiraClient = {
        searchJql: jest.fn().mockRejectedValue(new Error('Invalid project key')),
      };
      const integrator = new JiraIntegrator('your-jira-token', 'https://your-jira-instance.atlassian.net');
      await expect(integrator.getProjectIssues('INVALID-PROJECT-KEY')).to.be.rejected;
    });
  });

  describe('addTask', () => {
    it('should add a task to the project', async () => {
      const mockJiraClient = {
        createIssue: jest.fn().mockResolvedValue({ id: '789' }),
      };
      const integrator = new JiraIntegrator('your-jira-token', 'https://your-jira-instance.atlassian.net');
      const task = new Task('', 'New Task', 'This is a new task.', 'To Do');
      await integrator.addTask(task);
      expect(task.id).to.equal('789');
    });

    it('should throw an error if the project key is invalid', async () => {
      const mockJiraClient = {
        createIssue: jest.fn().mockRejectedValue(new Error('Invalid project key')),
      };
      const integrator = new JiraIntegrator('your-jira-token', 'https://your-jira-instance.atlassian.net');
      await expect(integrator.addTask(new Task('', 'New Task', 'This is a new task.', 'To Do'))).to.be.rejected;
    });
  });

  describe('isNumber', () => {
    it('should return true for numbers', () => {
      const result = TypeSystem.isNumber(42);
      expect(result).to.equal(true);
    });

    it('should return false for non-number values', () => {
      const result = TypeSystem.isNumber('hello');
      expect(result).to.equal(false);
    });
  });

  describe('isString', () => {
    it('should return true for strings', () => {
      const result = TypeSystem.isString('world');
      expect(result).to.equal(true);
    });

    it('should return false for non-string values', () => {
      const result = TypeSystem.isString(42);
      expect(result).to.equal(false);
    });
  });

  describe('isArray', () => {
    it('should return true for arrays', () => {
      const result = TypeSystem.isArray([1, 2, 3]);
      expect(result).to.equal(true);
    });

    it('should return false for non-array values', () => {
      const result = TypeSystem.isArray(42);
      expect(result).to.equal(false);
    });
  });
});