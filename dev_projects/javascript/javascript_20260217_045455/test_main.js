const axios = require('axios');
const { expect } = require('chai');

describe('JiraClient', () => {
  let jiraClient;

  beforeEach(() => {
    jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');
  });

  describe('createIssue', () => {
    it('should create a new issue with valid data', async () => {
      const title = 'New Task';
      const description = 'This is a new task description';

      const response = await jiraClient.createIssue(title, description);

      expect(response).to.have.property('key');
      expect(response.fields.summary).to.equal(title);
      expect(response.fields.description).to.equal(description);
    });

    it('should throw an error if the project key is invalid', async () => {
      const title = 'New Task';
      const description = 'This is a new task description';

      try {
        await jiraClient.createIssue(title, description, { project: { key: 'INVALID_PROJECT_KEY' } });
      } catch (error) {
        expect(error.message).to.equal('Failed to create issue: Project key is invalid');
      }
    });

    it('should throw an error if the summary is empty', async () => {
      const title = '';
      const description = 'This is a new task description';

      try {
        await jiraClient.createIssue(title, description);
      } catch (error) {
        expect(error.message).to.equal('Failed to create issue: Summary cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid data', async () => {
      const title = 'Updated Task';
      const description = 'This is an updated task description';

      const response = await jiraClient.updateIssue('ISSUE_KEY', title, description);

      expect(response).to.have.property('key');
      expect(response.fields.summary).to.equal(title);
      expect(response.fields.description).to.equal(description);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const title = 'Updated Task';
      const description = 'This is an updated task description';

      try {
        await jiraClient.updateIssue('INVALID_ISSUE_KEY', title, description);
      } catch (error) {
        expect(error.message).to.equal('Failed to update issue: Issue key is invalid');
      }
    });

    it('should throw an error if the summary is empty', async () => {
      const title = '';
      const description = 'This is an updated task description';

      try {
        await jiraClient.updateIssue('ISSUE_KEY', title, description);
      } catch (error) {
        expect(error.message).to.equal('Failed to update issue: Summary cannot be empty');
      }
    });
  });

  describe('getIssue', () => {
    it('should retrieve an existing issue with valid data', async () => {
      const response = await jiraClient.getIssue('ISSUE_KEY');

      expect(response).to.have.property('key');
      expect(response.fields.summary).to.equal('Task');
      expect(response.fields.description).to.equal('This is a new task description');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await jiraClient.getIssue('INVALID_ISSUE_KEY');
      } catch (error) {
        expect(error.message).to.equal('Failed to get issue: Issue key is invalid');
      }
    });
  });
});