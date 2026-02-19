const axios = require('axios');
const { JiraClient } = require('@jira/client');

describe('JiraClient', () => {
  describe('#getTasks', () => {
    it('should return tasks for the specified project', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock a response from axios
      jest.spyOn(axios, 'get').mockResolvedValue({
        data: {
          items: [
            { id: '12345', summary: 'Task 1' },
            { id: '67890', summary: 'Task 2' },
          ],
        },
      });

      const tasks = await jiraClient.getTasks();
      expect(tasks.length).toBe(2);
      expect(tasks[0].title).toBe('Task 1');
    });

    it('should handle errors when fetching tasks', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock an error response from axios
      jest.spyOn(axios, 'get').mockRejectedValue(new Error('Network error'));

      try {
        await jiraClient.getTasks();
      } catch (error) {
        expect(error.message).toBe('Network error');
      }
    });
  });

  describe('#createTask', () => {
    it('should create a new task with the specified title', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock a response from axios
      jest.spyOn(axios, 'post').mockResolvedValue({
        data: {
          id: '12345',
          summary: 'New Task',
          issuetype: { name: 'Bug' },
        },
      });

      const newTask = await jiraClient.createTask('New Bug');
      expect(newTask.id).toBe('12345');
      expect(newTask.title).toBe('New Task');
    });

    it('should handle errors when creating a task', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock an error response from axios
      jest.spyOn(axios, 'post').mockRejectedValue(new Error('Invalid title'));

      try {
        await jiraClient.createTask('New Bug');
      } catch (error) {
        expect(error.message).toBe('Invalid title');
      }
    });
  });

  describe('#updateTask', () => {
    it('should update an existing task with the specified title', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock a response from axios
      jest.spyOn(axios, 'put').mockResolvedValue({
        data: {
          id: '12345',
          summary: 'Updated Task',
          issuetype: { name: 'Bug' },
        },
      });

      const updatedTask = await jiraClient.updateTask('12345', 'Updated Bug');
      expect(updatedTask.id).toBe('12345');
      expect(updatedTask.title).toBe('Updated Task');
    });

    it('should handle errors when updating a task', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock an error response from axios
      jest.spyOn(axios, 'put').mockRejectedValue(new Error('Task not found'));

      try {
        await jiraClient.updateTask('12345', 'Updated Bug');
      } catch (error) {
        expect(error.message).toBe('Task not found');
      }
    });
  });

  describe('#deleteTask', () => {
    it('should delete an existing task', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock a response from axios
      jest.spyOn(axios, 'delete').mockResolvedValue({ status: 204 });

      await jiraClient.deleteTask('12345');
    });

    it('should handle errors when deleting a task', async () => {
      const config = new JiraConfig('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
      const jiraClient = new JiraClientImpl(config);

      // Mock an error response from axios
      jest.spyOn(axios, 'delete').mockRejectedValue(new Error('Task not found'));

      try {
        await jiraClient.deleteTask('12345');
      } catch (error) {
        expect(error.message).toBe('Task not found');
      }
    });
  });
});