const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

describe('JiraClient', () => {
  describe('createIssue', () => {
    it('should create an issue with valid fields', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const title = 'Test Issue';
      const description = 'This is a test issue for the JavaScript Agent tracking feature.';
      const response = await client.createIssue(title, description);
      expect(response).toHaveProperty('id');
    });

    it('should throw an error when creating an issue with invalid fields', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const title = '';
      const description = 'This is a test issue for the JavaScript Agent tracking feature.';
      await expect(client.createIssue(title, description)).rejects.toThrowError('Erro ao criar o issue:');
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid fields', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const issueId = uuidv4();
      const title = 'Updated Issue';
      const description = 'This is an updated test issue for the JavaScript Agent tracking feature.';
      await client.createIssue(title, description);
      const response = await client.updateIssue(issueId, title, description);
      expect(response).toHaveProperty('id');
    });

    it('should throw an error when updating an issue with invalid fields', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const issueId = uuidv4();
      const title = '';
      const description = 'This is an updated test issue for the JavaScript Agent tracking feature.';
      await expect(client.updateIssue(issueId, title, description)).rejects.toThrowError('Erro ao atualizar o issue:');
    });
  });

  describe('getIssue', () => {
    it('should retrieve an existing issue with valid fields', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const issueId = uuidv4();
      await client.createIssue('Test Issue', 'This is a test issue for the JavaScript Agent tracking feature.');
      const response = await client.getIssue(issueId);
      expect(response).toHaveProperty('id');
    });

    it('should throw an error when retrieving an non-existing issue', async () => {
      const client = new JiraClient('YOUR_API_TOKEN');
      const issueId = uuidv4();
      await expect(client.getIssue(issueId)).rejects.toThrowError('Erro ao obter o issue:');
    });
  });
});

describe('JavaScriptAgent', () => {
  describe('startTracking', () => {
    it('should create an issue with valid fields and start tracking', async () => {
      const apiToken = 'YOUR_API_TOKEN';
      const jiraClient = new JiraClient(apiToken);
      const javascriptAgent = new JavaScriptAgent(apiToken, jiraClient);
      await javascriptAgent.startTracking();
    });

    it('should throw an error when starting tracking with invalid fields', async () => {
      const apiToken = 'YOUR_API_TOKEN';
      const jiraClient = new JiraClient(apiToken);
      const javascriptAgent = new JavaScriptAgent(apiToken, jiraClient);
      await expect(javascriptAgent.startTracking()).rejects.toThrowError('Erro ao iniciar o tracking:');
    });
  });

  describe('stopTracking', () => {
    it('should create an issue with valid fields and stop tracking', async () => {
      const apiToken = 'YOUR_API_TOKEN';
      const jiraClient = new JiraClient(apiToken);
      const javascriptAgent = new JavaScriptAgent(apiToken, jiraClient);
      await javascriptAgent.stopTracking();
    });

    it('should throw an error when stopping tracking with invalid fields', async () => {
      const apiToken = 'YOUR_API_TOKEN';
      const jiraClient = new JiraClient(apiToken);
      const javascriptAgent = new JavaScriptAgent(apiToken, jiraClient);
      await expect(javascriptAgent.stopTracking()).rejects.toThrowError('Erro ao parar o tracking:');
    });
  });
});