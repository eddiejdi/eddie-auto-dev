// Import necessary libraries and modules
const axios = require('axios');
const fs = require('fs');

// Define the JavaScript Agent class
class JavaScriptAgent {
  constructor(options) {
    this.options = options;
  }

  // Method to send a request to Jira API
  async sendRequest(url, method, data) {
    try {
      const response = await axios({
        url,
        method,
        data,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.options.token}`
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Error sending request to Jira API: ${error.message}`);
    }
  }

  // Method to track an activity in Jira
  async trackActivity(activityData) {
    try {
      const url = `${this.options.jiraUrl}/rest/api/2/issue`;
      const response = await this.sendRequest(url, 'POST', activityData);
      console.log('Activity tracked successfully:', response);
    } catch (error) {
      throw new Error(`Error tracking activity: ${error.message}`);
    }
  }

  // Method to log an error in Jira
  async logError(errorData) {
    try {
      const url = `${this.options.jiraUrl}/rest/api/2/issue`;
      const response = await this.sendRequest(url, 'POST', errorData);
      console.log('Error logged successfully:', response);
    } catch (error) {
      throw new Error(`Error logging error: ${error.message}`);
    }
  }

  // Main function to run the JavaScript Agent
  async main() {
    try {
      const activityData = {
        fields: {
          summary: 'New task created',
          description: 'This is a new task created by the JavaScript Agent'
        }
      };
      await this.trackActivity(activityData);

      const errorData = {
        fields: {
          summary: 'Error occurred',
          description: 'An error occurred while trying to create the task'
        }
      };
      await this.logError(errorData);
    } catch (error) {
      console.error('Main function failed:', error.message);
    }
  }
}

// Example usage
const options = {
  token: 'your-jira-token',
  jiraUrl: 'https://your-jira-instance.atlassian.net'
};

const agent = new JavaScriptAgent(options);

(async () => {
  await agent.main();
})();