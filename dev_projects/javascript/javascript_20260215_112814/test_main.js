const axios = require('axios');
const { createLogger, format } = require('winston');

// Configuração do Winston para logs
const logger = createLogger({
  level: 'info',
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'app.log' })
  ],
  format: format.simple()
});

class JiraClient {
  constructor(options) {
    this.options = options;
  }

  async login() {
    const response = await axios.post(`${this.options.url}/rest/api/2/session`, {
      username: this.options.username,
      password: this.options.password
    });
    return response.data.session.token;
  }

  async createIssue(issueData) {
    const token = await this.login();
    const response = await axios.post(`${this.options.url}/rest/api/2/issue`, {
      fields: issueData
    }, { headers: { 'X-Atlassian-Token': token } });
    return response.data;
  }
}

class JavaScriptAgent {
  constructor(options) {
    this.options = options;
  }

  async trackActivity(activity) {
    const jiraClient = new JiraClient(this.options.jira);
    try {
      await jiraClient.createIssue({
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: activity.summary,
        description: activity.description
      });
      logger.info(`Activity tracked successfully: ${activity.summary}`);
    } catch (error) {
      logger.error(`Error tracking activity: ${error.message}`);
    }
  }
}

// Exemplo de uso
const options = {
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password',
  jira: {
    url: 'https://your-jira-instance.atlassian.net'
  }
};

const activity = {
  summary: 'New feature implemented',
  description: 'Added a new route and controller to the application.'
};

const javascriptAgent = new JavaScriptAgent(options);
javascriptAgent.trackActivity(activity);

// Testes
describe('JiraClient', () => {
  describe('login', () => {
    it('should return a token on successful login', async () => {
      const mockResponse = { session: { token: 'mock-token' } };
      jest.spyOn(axios, 'post').mockResolvedValue(mockResponse);
      const result = await new JiraClient({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' }).login();
      expect(result).toEqual('mock-token');
    });

    it('should throw an error on failed login', async () => {
      const mockError = new Error('Login failed');
      jest.spyOn(axios, 'post').mockRejectedValue(mockError);
      await expect(new JiraClient({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' }).login()).rejects.toThrow('Login failed');
    });
  });

  describe('createIssue', () => {
    it('should create an issue on successful creation', async () => {
      const mockResponse = { id: '12345' };
      jest.spyOn(axios, 'post').mockResolvedValue(mockResponse);
      const result = await new JiraClient({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' }).createIssue({
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: activity.summary,
        description: activity.description
      });
      expect(result).toEqual('12345');
    });

    it('should throw an error on failed creation', async () => {
      const mockError = new Error('Issue creation failed');
      jest.spyOn(axios, 'post').mockRejectedValue(mockError);
      await expect(new JiraClient({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password' }).createIssue({
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: activity.summary,
        description: activity.description
      })).rejects.toThrow('Issue creation failed');
    });
  });
});

describe('JavaScriptAgent', () => {
  describe('trackActivity', () => {
    it('should track an activity on successful tracking', async () => {
      const mockResponse = { id: '12345' };
      jest.spyOn(axios, 'post').mockResolvedValue(mockResponse);
      await new JavaScriptAgent({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password', jira: { url: 'https://your-jira-instance.atlassian.net' } }).trackActivity(activity);
      expect(logger.info).toHaveBeenCalledWith(`Activity tracked successfully: ${activity.summary}`);
    });

    it('should throw an error on failed tracking', async () => {
      const mockError = new Error('Activity tracking failed');
      jest.spyOn(axios, 'post').mockRejectedValue(mockError);
      await expect(new JavaScriptAgent({ url: 'https://your-jira-instance.atlassian.net', username: 'your-username', password: 'your-password', jira: { url: 'https://your-jira-instance.atlassian.net' } }).trackActivity(activity)).rejects.toThrow('Activity tracking failed');
    });
  });
});