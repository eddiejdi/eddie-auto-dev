import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('JiraClient', () => {
  describe('#getTasks()', () => {
    it('should return an array of tasks when successful', async () => {
      const client = new JiraClientImpl('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const tasks = await client.getTasks();
      expect(tasks).to.be.an.array;
      expect(tasks.length).to.be.greaterThan(0);
    });

    it('should throw an error when the request fails', async () => {
      const client = new JiraClientImpl('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      try {
        await client.getTasks();
      } catch (error) {
        expect(error).to.be.an(Error);
        expect(error.message).to.contain('Failed to fetch tasks');
      }
    });
  });

  describe('#updateTask()', () => {
    it('should update a task when successful', async () => {
      const client = new JiraClientImpl('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      await client.updateTask('ABC123', 'In Progress');
      // Add assertions to verify that the task status has been updated
    });

    it('should throw an error when the request fails', async () => {
      const client = new JiraClientImpl('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      try {
        await client.updateTask('ABC123', 'In Progress');
      } catch (error) {
        expect(error).to.be.an(Error);
        expect(error.message).to.contain('Failed to update task');
      }
    });
  });
});