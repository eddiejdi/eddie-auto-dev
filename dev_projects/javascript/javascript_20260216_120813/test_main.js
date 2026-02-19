const axios = require('axios');
const { expect } = require('chai');

describe('JiraClient', () => {
  let jiraClient;

  beforeEach(() => {
    jiraClient = new JiraClient('your-api-key', 'https://your-jira-server.com');
  });

  describe('#getIssues', () => {
    it('should return issues when successful', async () => {
      const response = await axios.get(`${jiraClient.serverUrl}/rest/api/2/search`, {
        params: {
          jql: 'project = MyProject',
          fields: ['summary', 'status'],
        },
        headers: {
          'Authorization': `Basic ${Buffer.from(`${jiraClient.apiKey}:`).toString('base64')}`,
        },
      });

      expect(response.status).to.equal(200);
      expect(response.data.issues.length).to.be.greaterThan(0);
    });

    it('should throw an error when API call fails', async () => {
      axios.get = jest.fn().rejects(new Error('API call failed'));

      try {
        await jiraClient.getIssues();
      } catch (error) {
        expect(error.message).to.equal('API call failed');
      }
    });
  });

  describe('#createIssue', () => {
    it('should create an issue when successful', async () => {
      const response = await axios.post(`${jiraClient.serverUrl}/rest/api/2/issue`, {
        fields: {
          project: { key: 'MyProject' },
          summary,
          description,
          status: { name: 'Open' },
        },
      });

      expect(response.status).to.equal(201);
      expect(response.data.key).to.not.be.null;
    });

    it('should throw an error when API call fails', async () => {
      axios.post = jest.fn().rejects(new Error('API call failed'));

      try {
        await jiraClient.createIssue(summary, description);
      } catch (error) {
        expect(error.message).to.equal('API call failed');
      }
    });
  });
});