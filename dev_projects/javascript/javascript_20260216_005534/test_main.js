const axios = require('axios');
const JiraClient = require('./JiraClient');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient('https://your-jira-url.com', 'your-api-token');
  });

  describe('#getIssues', () => {
    it('should return issues for a valid query', async () => {
      const response = await client.getIssues('summary~contains("bug")');
      expect(response).toHaveProperty('issues');
      expect(response.issues.length).toBeGreaterThan(0);
    });

    it('should throw an error if the query is invalid', async () => {
      try {
        await client.getIssues('invalid-query');
      } catch (error) {
        expect(error.message).toContain('Failed to fetch issues');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an issue with valid data', async () => {
      const issueId = '12345';
      const newData = { summary: 'Updated bug' };
      const response = await client.updateIssue(issueId, newData);
      expect(response).toHaveProperty('id');
      expect(response.id).toBe(issueId);
    });

    it('should throw an error if the issue does not exist', async () => {
      try {
        await client.updateIssue('invalid-issue-id', { summary: 'Updated bug' });
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });
  });

  describe('#createIssue', () => {
    it('should create a new issue with valid data', async () => {
      const newData = { summary: 'New bug', description: 'This is a new bug' };
      const response = await client.createIssue(newData);
      expect(response).toHaveProperty('id');
      expect(response.id).toBeGreaterThan(0);
    });

    it('should throw an error if the data is invalid', async () => {
      try {
        await client.createIssue({ summary: 'New bug' });
      } catch (error) {
        expect(error.message).toContain('Failed to create issue');
      }
    });
  });

  describe('#deleteIssue', () => {
    it('should delete an existing issue with valid data', async () => {
      const issueId = '12345';
      const response = await client.deleteIssue(issueId);
      expect(response).toHaveProperty('id');
      expect(response.id).toBe(issueId);
    });

    it('should throw an error if the issue does not exist', async () => {
      try {
        await client.deleteIssue('invalid-issue-id');
      } catch (error) {
        expect(error.message).toContain('Failed to delete issue');
      }
    });
  });
});