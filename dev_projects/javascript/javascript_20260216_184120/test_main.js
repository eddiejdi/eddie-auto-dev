const axios = require('axios');
const { JiraClient } = require('@atlassian/jira-client');

describe('integrateJavaScriptAgentWithJira', () => {
  let jiraClient;

  beforeEach(() => {
    jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      options: {
        host: 'your_jira_host',
        port: your_jira_port,
        protocol: 'https'
      }
    });
  });

  describe('integrateJavaScriptAgentWithJira', () => {
    it('should retrieve activities from Jira', async () => {
      const activities = await jiraClient.searchActivities({
        query: 'type=issue AND status!=closed',
        fields: ['summary', 'status']
      });

      expect(activities.items.length).toBeGreaterThan(0);
      expect(activities.items[0].fields.summary).toBeDefined();
      expect(activities.items[0].fields.status).toBeDefined();
    });

    it('should create an event in Jira', async () => {
      const issueKey = 'YOUR_ISSUE_KEY';
      const comment = 'This is an example comment from JavaScript Agent.';
      const event = await jiraClient.createEvent({
        issueKey,
        type: 'issueCommented',
        fields: {
          comment
        }
      });

      expect(event).toBeDefined();
    });
  });
});