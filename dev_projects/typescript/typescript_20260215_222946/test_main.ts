import { expect } from 'chai';
import axios from 'axios';

describe('JiraClient', () => {
  let client: JiraClient;

  beforeEach(() => {
    const apiUrl = 'https://your-jira-instance.atlassian.net';
    const token = 'your-jira-token';
    client = new JiraClient(apiUrl, token);
  });

  describe('getIssues', () => {
    it('should return issues when the query is valid', async () => {
      const response = await client.getIssues('status = open');
      expect(response).to.be.an.array;
    });

    it('should throw an error when the query is invalid', async () => {
      try {
        await client.getIssues('invalid_query');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid JQL query');
      }
    });
  });

  describe('createIssue', () => {
    it('should create an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          project: { key: 'YOUR-PROJECT-KEY' },
          summary: 'New Scrum Task',
          description: 'This is a new task for the Scrum project.',
          issuetype: { name: 'Task' }
        }
      };
      const response = await client.createIssue(issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await client.createIssue({});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          description: 'This is an updated task for the Scrum project.'
        }
      };
      const response = await client.updateIssue('ISSUE-KEY', issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await client.updateIssue('ISSUE-KEY', {});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue when the key is valid', async () => {
      const response = await client.deleteIssue('ISSUE-KEY');
      expect(response).to.have.property('key');
    });

    it('should throw an error when the key is invalid', async () => {
      try {
        await client.deleteIssue('INVALID-KEY');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue key');
      }
    });
  });
});

describe('ScrumBoard', () => {
  let board: ScrumBoard;

  beforeEach(() => {
    const apiUrl = 'https://your-jira-instance.atlassian.net';
    const token = 'your-jira-token';
    client = new JiraClient(apiUrl, token);
    board = new ScrumBoard(client);
  });

  describe('fetchIssues', () => {
    it('should return issues when the query is valid', async () => {
      const response = await board.fetchIssues('status = open');
      expect(response).to.be.an.array;
    });

    it('should throw an error when the query is invalid', async () => {
      try {
        await board.fetchIssues('invalid_query');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid JQL query');
      }
    });
  });

  describe('createIssue', () => {
    it('should create an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          project: { key: 'YOUR-PROJECT-KEY' },
          summary: 'New Scrum Task',
          description: 'This is a new task for the Scrum project.',
          issuetype: { name: 'Task' }
        }
      };
      const response = await board.createIssue(issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await board.createIssue({});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          description: 'This is an updated task for the Scrum project.'
        }
      };
      const response = await board.updateIssue('ISSUE-KEY', issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await board.updateIssue('ISSUE-KEY', {});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue when the key is valid', async () => {
      const response = await board.deleteIssue('ISSUE-KEY');
      expect(response).to.have.property('key');
    });

    it('should throw an error when the key is invalid', async () => {
      try {
        await board.deleteIssue('INVALID-KEY');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue key');
      }
    });
  });
});

describe('ScrumProject', () => {
  let project: ScrumProject;

  beforeEach(() => {
    const apiUrl = 'https://your-jira-instance.atlassian.net';
    const token = 'your-jira-token';
    client = new JiraClient(apiUrl, token);
    board = new ScrumBoard(client);
    project = new ScrumProject('Scrum Project', board);
  });

  describe('fetchIssues', () => {
    it('should return issues when the query is valid', async () => {
      const response = await project.fetchIssues('status = open');
      expect(response).to.be.an.array;
    });

    it('should throw an error when the query is invalid', async () => {
      try {
        await project.fetchIssues('invalid_query');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid JQL query');
      }
    });
  });

  describe('createIssue', () => {
    it('should create an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          project: { key: 'YOUR-PROJECT-KEY' },
          summary: 'New Scrum Task',
          description: 'This is a new task for the Scrum project.',
          issuetype: { name: 'Task' }
        }
      };
      const response = await project.createIssue(issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await project.createIssue({});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue when the data is valid', async () => {
      const issueData = {
        fields: {
          description: 'This is an updated task for the Scrum project.'
        }
      };
      const response = await project.updateIssue('ISSUE-KEY', issueData);
      expect(response).to.have.property('key');
    });

    it('should throw an error when the data is invalid', async () => {
      try {
        await project.updateIssue('ISSUE-KEY', {});
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue data');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue when the key is valid', async () => {
      const response = await project.deleteIssue('ISSUE-KEY');
      expect(response).to.have.property('key');
    });

    it('should throw an error when the key is invalid', async () => {
      try {
        await project.deleteIssue('INVALID-KEY');
      } catch (error) {
        expect(error).to.have.property('message', 'Invalid issue key');
      }
    });
  });
});