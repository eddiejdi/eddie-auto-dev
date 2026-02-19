const axios = require('axios');
const { promisify } = require('util');

// Function to send a request to Jira's JavaScript Agent API
async function sendToJiraAgent(url, data) {
  try {
    const response = await axios.post(url, data);
    return response.data;
  } catch (error) {
    console.error('Error sending to Jira Agent:', error);
    throw error;
  }
}

// Class representing the JavaScript Agent
class JavaScriptAgent {
  constructor(options) {
    this.options = options || {};
    this.url = this.options.url || 'http://localhost:8080/api/agent';
  }

  // Method to track an activity in Jira
  async trackActivity(activityData) {
    try {
      const response = await sendToJiraAgent(this.url, activityData);
      console.log('Activity tracked successfully:', response);
    } catch (error) {
      throw error;
    }
  }
}

// Main function to run the JavaScript Agent
async function main() {
  const agentOptions = {
    url: 'http://localhost:8080/api/agent'
  };

  const agent = new JavaScriptAgent(agentOptions);

  try {
    await agent.trackActivity({
      activityType: 'task',
      taskId: '12345',
      status: 'completed'
    });
  } catch (error) {
    console.error('Error tracking activity:', error);
  }
}

// Check if the script is run directly
if (require.main === module) {
  main();
}