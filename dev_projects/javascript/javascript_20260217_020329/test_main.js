const axios = require('axios');
const { exec } = require('child_process');

// Define the main function
async function main() {
  try {
    // Configure the JavaScript Agent
    await configureJavaScriptAgent();

    // Monitor activities in Jira
    await monitorActivitiesInJira();
  } catch (error) {
    console.error('Error:', error);
  }
}

// Function to configure the JavaScript Agent
async function configureJavaScriptAgent() {
  try {
    const response = await axios.post('https://your-jira-instance/rest/api/2/agent', {
      name: 'My JavaScript Agent',
      version: '1.0',
      enabled: true,
      properties: {
        // Add your JavaScript Agent properties here
      }
    });

    console.log('JavaScript Agent configured successfully:', response.data);
  } catch (error) {
    throw new Error('Failed to configure JavaScript Agent:', error);
  }
}

// Function to monitor activities in Jira
async function monitorActivitiesInJira() {
  try {
    const response = await axios.get('https://your-jira-instance/rest/api/2/issue/search', {
      jql: 'status = Open',
      fields: ['summary', 'assignee']
    });

    if (response.data.total > 0) {
      console.log('Activities in Jira:');
      response.data.issues.forEach(issue => {
        console.log(`- ${issue.fields.summary} by ${issue.fields.assignee.name}`);
      });
    } else {
      console.log('No activities found in Jira.');
    }
  } catch (error) {
    throw new Error('Failed to monitor activities in Jira:', error);
  }
}

// Execute the main function
main();