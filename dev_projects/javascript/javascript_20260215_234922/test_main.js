const axios = require('axios');
const JiraClient = require('./JiraClient');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient('your-api-token');
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const title = 'Test Issue';
      const description = 'This is a test issue.';
      const response = await client.createIssue(title, description);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the title or description is invalid', async () => {
      try {
        await client.createIssue('', '');
      } catch (error) {
        expect(error.message).toContain('Invalid issue data');
      }
    });
  });

  describe('getIssue', () => {
    it('should retrieve an issue by key', async () => {
      const issueKey = 'TEST-1';
      const response = await client.getIssue(issueKey);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.getIssue('');
      } catch (error) {
        expect(error.message).toContain('Invalid issue key');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const issueKey = 'TEST-1';
      const fields = { description: 'Updated test issue.' };
      const response = await client.updateIssue(issueKey, fields);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key or fields are invalid', async () => {
      try {
        await client.updateIssue('', {});
      } catch (error) {
        expect(error.message).toContain('Invalid issue data');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue by key', async () => {
      const issueKey = 'TEST-1';
      const response = await client.deleteIssue(issueKey);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await client.deleteIssue('');
      } catch (error) {
        expect(error.message).toContain('Invalid issue key');
      }
    });
  });
});