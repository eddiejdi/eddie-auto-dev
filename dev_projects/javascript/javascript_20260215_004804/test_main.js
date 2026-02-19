const axios = require('axios');
const JiraClient = require('./JiraClient');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient('your_api_token', 'https://your_jira_url');
  });

  describe('#createIssue', () => {
    it('should create an issue with valid data', async () => {
      const title = 'Test Issue';
      const description = 'This is a test issue created by the JavaScript Agent.';
      const response = await client.createIssue(title, description);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the API token is invalid', async () => {
      const title = 'Test Issue';
      const description = 'This is a test issue created by the JavaScript Agent.';
      try {
        await client.createIssue(title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to create issue');
      }
    });

    it('should throw an error if the URL is invalid', async () => {
      const title = 'Test Issue';
      const description = 'This is a test issue created by the JavaScript Agent.';
      try {
        client = new JiraClient('your_api_token', 'https://invalid_url');
        await client.createIssue(title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to create issue');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const issueId = '12345';
      const title = 'Updated Test Issue';
      const description = 'This is an updated test issue created by the JavaScript Agent.';
      const response = await client.updateIssue(issueId, title, description);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the API token is invalid', async () => {
      const issueId = '12345';
      const title = 'Updated Test Issue';
      const description = 'This is an updated test issue created by the JavaScript Agent.';
      try {
        await client.updateIssue(issueId, title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });

    it('should throw an error if the URL is invalid', async () => {
      const issueId = '12345';
      const title = 'Updated Test Issue';
      const description = 'This is an updated test issue created by the JavaScript Agent.';
      try {
        client = new JiraClient('your_api_token', 'https://invalid_url');
        await client.updateIssue(issueId, title, description);
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });
  });

  describe('#getIssue', () => {
    it('should retrieve an existing issue with valid data', async () => {
      const issueId = '12345';
      const response = await client.getIssue(issueId);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the API token is invalid', async () => {
      const issueId = '12345';
      try {
        await client.getIssue(issueId);
      } catch (error) {
        expect(error.message).toContain('Failed to get issue');
      }
    });

    it('should throw an error if the URL is invalid', async () => {
      const issueId = '12345';
      try {
        client = new JiraClient('your_api_token', 'https://invalid_url');
        await client.getIssue(issueId);
      } catch (error) {
        expect(error.message).toContain('Failed to get issue');
      }
    });
  });

  describe('#deleteIssue', () => {
    it('should delete an existing issue with valid data', async () => {
      const issueId = '12345';
      const response = await client.deleteIssue(issueId);
      expect(response).toHaveProperty('key');
    });

    it('should throw an error if the API token is invalid', async () => {
      const issueId = '12345';
      try {
        await client.deleteIssue(issueId);
      } catch (error) {
        expect(error.message).toContain('Failed to delete issue');
      }
    });

    it('should throw an error if the URL is invalid', async () => {
      const issueId = '12345';
      try {
        client = new JiraClient('your_api_token', 'https://invalid_url');
        await client.deleteIssue(issueId);
      } catch (error) {
        expect(error.message).toContain('Failed to delete issue');
      }
    });
  });
});