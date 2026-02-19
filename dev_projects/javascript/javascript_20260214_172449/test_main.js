const axios = require('axios');
const JiraClient = require('./JiraClient');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });
  });

  describe('#createIssue', () => {
    it('should create an issue with valid data', async () => {
      const issueData = {
        projectKey: 'PROJ',
        summary: 'Test Issue',
        description: 'This is a test issue.',
        issuetype: { name: 'Bug' }
      };

      try {
        const response = await client.createIssue(issueData);
        expect(response).toHaveProperty('key');
      } catch (error) {
        throw new Error(`Failed to create issue: ${error.message}`);
      }
    });

    it('should fail to create an issue with invalid data', async () => {
      const issueData = {
        projectKey: 'PROJ',
        summary: '',
        description: '',
        issuetype: { name: '' }
      };

      try {
        await client.createIssue(issueData);
        throw new Error('Expected error');
      } catch (error) {
        expect(error.message).toContain('Failed to create issue');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const issueId = '12345';
      const issueData = {
        summary: 'Updated Test Issue',
        description: 'This is an updated test issue.',
        issuetype: { name: 'Bug' }
      };

      try {
        const response = await client.updateIssue(issueId, issueData);
        expect(response).toHaveProperty('key');
      } catch (error) {
        throw new Error(`Failed to update issue: ${error.message}`);
      }
    });

    it('should fail to update an existing issue with invalid data', async () => {
      const issueId = '12345';
      const issueData = {
        summary: '',
        description: '',
        issuetype: { name: '' }
      };

      try {
        await client.updateIssue(issueId, issueData);
        throw new Error('Expected error');
      } catch (error) {
        expect(error.message).toContain('Failed to update issue');
      }
    });
  });

  describe('#getIssue', () => {
    it('should retrieve an existing issue with valid data', async () => {
      const issueId = '12345';

      try {
        const response = await client.getIssue(issueId);
        expect(response).toHaveProperty('key');
      } catch (error) {
        throw new Error(`Failed to get issue: ${error.message}`);
      }
    });

    it('should fail to retrieve an existing issue with invalid data', async () => {
      const issueId = '12345';

      try {
        await client.getIssue(issueId);
        throw new Error('Expected error');
      } catch (error) {
        expect(error.message).toContain('Failed to get issue');
      }
    });
  });

  describe('#closeIssue', () => {
    it('should close an existing issue with valid data', async () => {
      const issueId = '12345';

      try {
        const response = await client.closeIssue(issueId);
        expect(response).toHaveProperty('key');
      } catch (error) {
        throw new Error(`Failed to close issue: ${error.message}`);
      }
    });

    it('should fail to close an existing issue with invalid data', async () => {
      const issueId = '12345';

      try {
        await client.closeIssue(issueId);
        throw new Error('Expected error');
      } catch (error) {
        expect(error.message).toContain('Failed to close issue');
      }
    });
  });
});