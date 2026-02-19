const { expect } = require('chai');
const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

describe('JiraScrumb', () => {
  let jiraScrumb;

  beforeEach(() => {
    jiraScrumb = new JiraScrumb({
      username: 'YOUR_USERNAME',
      password: 'YOUR_PASSWORD',
      server: 'https://your-jira-server.atlassian.net'
    });
  });

  describe('login', () => {
    it('should return a response with status code 200', async () => {
      const response = await jiraScrumb.login();
      expect(response.status).to.equal(200);
    });

    it('should throw an error if the username or password is invalid', async () => {
      try {
        await jiraScrumb.login({ username: 'invalid', password: 'password' });
      } catch (error) {
        expect(error).to.be.an(Error);
      }
    });
  });

  describe('createIssue', () => {
    it('should return a response with status code 201', async () => {
      const title = 'New Bug Report';
      const description = 'This is a new bug report for testing purposes.';
      const issue = await jiraScrumb.createIssue(title, description);
      expect(issue.status).to.equal(201);
    });

    it('should throw an error if the title or description is invalid', async () => {
      try {
        await jiraScrumb.createIssue('', '');
      } catch (error) {
        expect(error).to.be.an(Error);
      }
    });
  });

  describe('updateIssue', () => {
    it('should return a response with status code 200', async () => {
      const title = 'New Bug Report';
      const description = 'This is a new bug report for testing purposes.';
      const issue = await jiraScrumb.createIssue(title, description);
      const updatedFields = {
        status: { name: 'In Progress' }
      };
      const response = await jiraScrumb.updateIssue(issue.id, updatedFields);
      expect(response.status).to.equal(200);
    });

    it('should throw an error if the issue ID or fields are invalid', async () => {
      try {
        await jiraScrumb.updateIssue('', {});
      } catch (error) {
        expect(error).to.be.an(Error);
      }
    });
  });

  describe('getIssues', () => {
    it('should return a response with status code 200', async () => {
      const issues = await jiraScrumb.getIssues();
      expect(issues.length).to.be.greaterThan(0);
    });

    it('should throw an error if the request fails', async () => {
      try {
        await jiraScrumb.getIssues({ url: 'invalid' });
      } catch (error) {
        expect(error).to.be.an(Error);
      }
    });
  });
});