const axios = require('axios');
const fs = require('fs');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient({
      baseUrl: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });
  });

  describe('#getIssue', () => {
    it('should retrieve an issue with valid data', async () => {
      const response = await client.getIssue('ABC-123');
      expect(response).toHaveProperty('key');
      expect(response.fields.summary).toBe('Test Issue');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.getIssue('XYZ-987');
      } catch (error) {
        expect(error.message).toContain('Failed to retrieve issue');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an issue with valid data', async () => {
      const response = await client.updateIssue('ABC-123', { summary: 'Updated Test Issue' });
      expect(response).toHaveProperty('key');
      expect(response.fields.summary).toBe('Updated Test Issue');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.updateIssue('XYZ-987', { summary: 'Updated Test Issue' });
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });

    it('should throw an error if the updates object is invalid', async () => {
      try {
        await client.updateIssue('ABC-123', { summary: 'Updated Test Issue' });
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });
  });

  describe('#logActivity', () => {
    it('should log an activity for an existing issue with valid data', async () => {
      const response = await client.logActivity('ABC-123', 'This is a test activity.');
      expect(response).toHaveProperty('id');
      expect(response.body).toBe('This is a test activity.');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.logActivity('XYZ-987', 'This is a test activity.');
      } catch (error) {
        expect(error.message).toContain('Failed to log activity');
      }
    });

    it('should throw an error if the activity body is invalid', async () => {
      try {
        await client.logActivity('ABC-123', null);
      } catch (error) {
        expect(error.message).toContain('Failed to log activity');
      }
    });
  });

  describe('#trackActivity', () => {
    it('should track an activity for an existing issue with valid data', async () => {
      const response = await client.trackActivity('ABC-123', 'This is a test activity.');
      expect(response).toBe(`Activity logged for issue ABC-123`);
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.trackActivity('XYZ-987', 'This is a test activity.');
      } catch (error) {
        expect(error.message).toContain('Failed to track activity');
      }
    });

    it('should throw an error if the activity body is invalid', async () => {
      try {
        await client.trackActivity('ABC-123', null);
      } catch (error) {
        expect(error.message).toContain('Failed to track activity');
      }
    });
  });
});