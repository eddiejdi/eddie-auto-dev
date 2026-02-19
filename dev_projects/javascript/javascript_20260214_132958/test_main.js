const axios = require('axios');
const fs = require('fs');

describe('JavaScriptAgent', () => {
  let agent;

  beforeEach(() => {
    agent = new JavaScriptAgent({
      jiraUrl: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password',
      projectKey: 'YOUR-PROJECT-KEY'
    });
  });

  describe('fetchActivityLogs', () => {
    it('should fetch activity logs for a given project key', async () => {
      // Simulate the axios.get response
      const mockResponse = {
        data: {
          results: [
            { id: '12345', summary: 'Task 1', status: { name: 'In Progress' } },
            { id: '67890', summary: 'Task 2', status: { name: 'To Do' } }
          ]
        }
      };

      jest.spyOn(axios, 'get').mockResolvedValue(mockResponse);

      const logs = await agent.fetchActivityLogs();
      expect(logs).toEqual([
        { id: '12345', summary: 'Task 1', status: 'In Progress' },
        { id: '67890', summary: 'Task 2', status: 'To Do' }
      ]);
    });

    it('should throw an error if the API request fails', async () => {
      // Simulate the axios.get response with an error
      const mockError = new Error('Network error');

      jest.spyOn(axios, 'get').mockRejectedValue(mockError);

      await expect(agent.fetchActivityLogs()).rejects.toThrowError('Failed to fetch activity logs');
    });
  });

  describe('trackActivity', () => {
    it('should track activity for a given list of logs', async () => {
      // Simulate the axios.post response
      const mockResponse = {
        data: { id: '12345', body: 'Tracking of Task 1, Task 2' }
      };

      jest.spyOn(axios, 'post').mockResolvedValue(mockResponse);

      const logs = [
        { id: '12345', summary: 'Task 1', status: 'In Progress' },
        { id: '67890', summary: 'Task 2', status: 'To Do' }
      ];

      const trackedResponse = await agent.trackActivity(logs);
      expect(trackedResponse).toEqual({ id: '12345', body: 'Tracking of Task 1, Task 2' });
    });

    it('should throw an error if the API request fails', async () => {
      // Simulate the axios.post response with an error
      const mockError = new Error('Network error');

      jest.spyOn(axios, 'post').mockRejectedValue(mockError);

      await expect(agent.trackActivity([])).rejects.toThrowError('Failed to track activity');
    });
  });

  describe('run', () => {
    it('should fetch and track activity for a given project key', async () => {
      // Simulate the axios.get response
      const mockResponse = {
        data: {
          results: [
            { id: '12345', summary: 'Task 1', status: { name: 'In Progress' } },
            { id: '67890', summary: 'Task 2', status: 'To Do' }
          ]
        }
      };

      jest.spyOn(axios, 'get').mockResolvedValue(mockResponse);

      const logs = await agent.fetchActivityLogs();
      expect(logs).toEqual([
        { id: '12345', summary: 'Task 1', status: 'In Progress' },
        { id: '67890', summary: 'Task 2', status: 'To Do' }
      ]);

      // Simulate the axios.post response
      const mockResponse = {
        data: { id: '12345', body: 'Tracking of Task 1, Task 2' }
      };

      jest.spyOn(axios, 'post').mockResolvedValue(mockResponse);

      await agent.run();
      expect(console.log).toHaveBeenCalledWith(`Tracked: ${mockResponse.body}`);
    });

    it('should handle no activity logs found', async () => {
      // Simulate the axios.get response with an empty array
      const mockResponse = {
        data: { results: [] }
      };

      jest.spyOn(axios, 'get').mockResolvedValue(mockResponse);

      await agent.run();
      expect(console.log).toHaveBeenCalledWith('No activity logs found');
    });
  });
});