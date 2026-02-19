const axios = require('axios');
const { JiraClient } = require('./JiraClient');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient('your-api-key', 'https://your-jira-server.com');
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      const response = await client.createIssue('Test Issue', 'This is a test issue.', 'TEST-123', 'Bug');
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the project key is invalid', async () => {
      try {
        await client.createIssue('Test Issue', 'This is a test issue.', 'INVALID-PROJECT', 'Bug');
      } catch (error) {
        expect(error.message).toContain('Failed to create issue: Project key is invalid');
      }
    });

    it('should throw an error if the issue type is invalid', async () => {
      try {
        await client.createIssue('Test Issue', 'This is a test issue.', 'TEST-123', 'INVALID-TYPE');
      } catch (error) {
        expect(error.message).toContain('Failed to create issue: Issue type is invalid');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const response = await client.updateIssue('TEST-123', 'Updated Test Issue', 'This is an updated test issue.');
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key does not exist', async () => {
      try {
        await client.updateIssue('INVALID-KEY', 'Updated Test Issue', 'This is an updated test issue.');
      } catch (error) {
        expect(error.message).toContain('Failed to update issue: Issue key does not exist');
      }
    });
  });

  describe('getIssue', () => {
    it('should retrieve an existing issue with valid data', async () => {
      const response = await client.getIssue('TEST-123');
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key does not exist', async () => {
      try {
        await client.getIssue('INVALID-KEY');
      } catch (error) {
        expect(error.message).toContain('Failed to get issue: Issue key does not exist');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue with valid data', async () => {
      const response = await client.deleteIssue('TEST-123');
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the issue key does not exist', async () => {
      try {
        await client.deleteIssue('INVALID-KEY');
      } catch (error) {
        expect(error.message).toContain('Failed to delete issue: Issue key does not exist');
      }
    });
  });
});