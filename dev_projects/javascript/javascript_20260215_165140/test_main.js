const axios = require('axios');
const assert = require('assert');

class JavaScriptAgent {
  constructor(jiraUrl, token) {
    this.jiraUrl = jiraUrl;
    this.token = token;
  }

  async trackActivity(issueKey, activityType, description) {
    try {
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue/${issueKey}/worklog`, {
        fields: {
          worklog: {
            comments: [
              {
                author: {
                  name: 'JavaScript Agent',
                  email: 'javascriptagent@example.com'
                },
                body: description
              }
            ],
            type: activityType,
            started: new Date().toISOString()
          }
        }
      }, {
        headers: {
          Authorization: `Basic ${Buffer.from(`${this.token}:`).toString('base64')}`
        }
      });

      console.log(response.data);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }
}

describe('JavaScriptAgent', () => {
  describe('#trackActivity', () => {
    it('should track an activity successfully with valid parameters', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const token = 'your-api-token';
      const issueKey = 'ABC-123';
      const activityType = 'Task Completed';
      const description = 'The task was completed successfully.';
      const agent = new JavaScriptAgent(jiraUrl, token);

      await agent.trackActivity(issueKey, activityType, description);
    });

    it('should throw an error if the issue key is invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const token = 'your-api-token';
      const issueKey = 'ABC-12345'; // Invalid issue key
      const activityType = 'Task Completed';
      const description = 'The task was completed successfully.';
      const agent = new JavaScriptAgent(jiraUrl, token);

      await assert.rejects(agent.trackActivity(issueKey, activityType, description), Error);
    });

    it('should throw an error if the activity type is invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const token = 'your-api-token';
      const issueKey = 'ABC-123';
      const activityType = 'Invalid Activity Type'; // Invalid activity type
      const description = 'The task was completed successfully.';
      const agent = new JavaScriptAgent(jiraUrl, token);

      await assert.rejects(agent.trackActivity(issueKey, activityType, description), Error);
    });

    it('should throw an error if the description is invalid', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const token = 'your-api-token';
      const issueKey = 'ABC-123';
      const activityType = 'Task Completed';
      const description = ''; // Empty string
      const agent = new JavaScriptAgent(jiraUrl, token);

      await assert.rejects(agent.trackActivity(issueKey, activityType, description), Error);
    });

    it('should throw an error if the request fails', async () => {
      const jiraUrl = 'https://your-jira-instance.atlassian.net';
      const token = 'your-api-token';
      const issueKey = 'ABC-123';
      const activityType = 'Task Completed';
      const description = 'The task was completed successfully.';
      const agent = new JavaScriptAgent(jiraUrl, token);

      await assert.rejects(agent.trackActivity(issueKey, activityType, description), Error);
    });
  });
});