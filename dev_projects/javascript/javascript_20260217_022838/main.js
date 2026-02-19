// Import necessary libraries
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

class JavaScriptAgent {
  constructor(jiraUrl, apiKey) {
    this.jiraUrl = jiraUrl;
    this.apiKey = apiKey;
  }

  async trackActivity(activityData) {
    try {
      // Generate a unique ID for the activity
      const activityId = uuidv4();

      // Prepare the request payload
      const payload = {
        issue: {
          key: 'YOUR_ISSUE_KEY', // Replace with your Jira issue key
          fields: {
            customfield_12345: activityData, // Replace with your custom field ID and data
          },
        },
      };

      // Send the request to Jira's REST API
      const response = await axios.post(`${this.jiraUrl}/rest/api/2/issue`, payload, {
        headers: {
          'Authorization': `Basic ${Buffer.from(`${this.apiKey}:x`).toString('base64')}`,
          'Content-Type': 'application/json',
        },
      });

      console.log(`Activity tracked successfully with ID: ${activityId}`);
    } catch (error) {
      console.error('Error tracking activity:', error);
    }
  }
}

// Example usage
const agent = new JavaScriptAgent('https://your-jira-instance.atlassian.net', 'YOUR_API_KEY');
const activityData = {
  description: 'This is a test activity',
  priority: 'High',
};

agent.trackActivity(activityData);