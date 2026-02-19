const axios = require('axios');
const { JiraClient } = require('@jira/client');

class JavaScriptAgent {
  constructor(jiraUrl, username, password) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
    this.client = new JiraClient({
      auth: {
        username: this.username,
        password: this.password
      }
    });
  }

  async monitorActivities() {
    try {
      const response = await this.client.get('rest/api/2/search', {
        fields: ['status'],
        jql: 'project = YOUR_PROJECT_KEY AND status not in (Done, Closed)'
      });

      const activities = response.data.items.map(item => ({
        id: item.id,
        title: item.fields.summary,
        status: item.fields.status.name
      }));

      console.log('Activities:', activities);
    } catch (error) {
      console.error('Error monitoring activities:', error);
    }
  }

  async registerEvent(event) {
    try {
      const response = await this.client.post('rest/api/2/issue', event);

      console.log('Event registered successfully:', response.data);
    } catch (error) {
      console.error('Error registering event:', error);
    }
  }
}

async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const agent = new JavaScriptAgent(jiraUrl, username, password);

  try {
    await agent.monitorActivities();
    // Example event to register
    const event = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: 'New task created',
        description: 'This is a new task created by the JavaScript Agent'
      }
    };

    await agent.registerEvent(event);
  } catch (error) {
    console.error('Main function error:', error);
  }
}

if (require.main === module) {
  main();
}