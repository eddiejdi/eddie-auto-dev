const axios = require('axios');
const { expect } = require('chai');

describe('JiraClient', () => {
  let client;

  beforeEach(() => {
    client = new JiraClient({
      baseUrl: 'https://your-jira-instance.atlassian.net',
      projectKey: 'YOUR-PROJECT-KEY'
    });
  });

  describe('#createIssue', () => {
    it('should create a new issue with valid data', async () => {
      const title = 'New Bug';
      const description = 'This is a new bug report.';
      const response = await client.createIssue(title, description);
      expect(response).to.have.property('id');
    });

    it('should throw an error if the title or description are empty', async () => {
      try {
        await client.createIssue('', '');
      } catch (error) {
        expect(error.message).to.equal('Title and description cannot be empty.');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const title = 'New Bug';
      const description = 'This is a new bug report.';
      const response = await client.createIssue(title, description);
      const updates = { status: 'In Progress' };
      const updatedResponse = await client.updateIssue(response.id, updates);
      expect(updatedResponse).to.have.property('status').equal('In Progress');
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await client.updateIssue('invalid-id', { status: 'In Progress' });
      } catch (error) {
        expect(error.message).to.equal('Invalid issue ID.');
      }
    });
  });

  describe('#getIssues', () => {
    it('should retrieve issues with valid status', async () => {
      const response = await client.getIssues('Open');
      expect(response.items.length).to.be.greaterThan(0);
    });

    it('should throw an error if the status is invalid', async () => {
      try {
        await client.getIssues('invalid-status');
      } catch (error) {
        expect(error.message).to.equal('Invalid status.');
      }
    });
  });
});