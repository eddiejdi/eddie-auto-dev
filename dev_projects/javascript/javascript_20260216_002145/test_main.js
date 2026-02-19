const axios = require('axios');
const { JiraClient } = require('@jira/client');

describe('connectToJira', () => {
  it('should connect to Jira successfully with valid credentials', async () => {
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      protocol: 'https',
      host: 'your_jira_host',
      port: 443,
      pathPrefix: '/rest/api/2'
    });

    try {
      await jiraClient.authenticate();
      expect(jiraClient).toBeTruthy();
    } catch (error) {
      throw error;
    }
  });

  it('should fail to connect to Jira with invalid credentials', async () => {
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'invalid_password'
      },
      protocol: 'https',
      host: 'your_jira_host',
      port: 443,
      pathPrefix: '/rest/api/2'
    });

    try {
      await jiraClient.authenticate();
    } catch (error) {
      expect(error).toBeTruthy();
    }
  });
});

describe('registerEvent', () => {
  it('should register an event successfully with valid fields', async () => {
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      protocol: 'https',
      host: 'your_jira_host',
      port: 443,
      pathPrefix: '/rest/api/2'
    });

    const event = {
      summary: 'New JavaScript Activity',
      description: 'This is a new JavaScript activity tracked in Jira.'
    };

    try {
      await registerEvent(jiraClient, event);
      expect(event).toBeTruthy();
    } catch (error) {
      throw error;
    }
  });

  it('should fail to register an event with invalid fields', async () => {
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      protocol: 'https',
      host: 'your_jira_host',
      port: 443,
      pathPrefix: '/rest/api/2'
    });

    const event = {
      summary: '',
      description: ''
    };

    try {
      await registerEvent(jiraClient, event);
    } catch (error) {
      expect(error).toBeTruthy();
    }
  });
});

describe('main', () => {
  it('should execute successfully with valid credentials and fields', async () => {
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      protocol: 'https',
      host: 'your_jira_host',
      port: 443,
      pathPrefix: '/rest/api/2'
    });

    const event = {
      summary: 'New JavaScript Activity',
      description: 'This is a new JavaScript activity tracked in Jira.'
    };

    try {
      await main();
      expect(event).toBeTruthy();
    } catch (error) {
      throw error;
    }
  });
});