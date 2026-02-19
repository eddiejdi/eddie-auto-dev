// Import necessary libraries and modules
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Define the main function to run the application
async function main() {
  // Create a new instance of the Jira client
  const jiraClient = new JiraClient({
    auth: {
      username: 'your_username',
      password: 'your_password'
    },
    protocol: 'https',
    host: 'your_jira_host'
  });

  try {
    // Log in to Jira
    await jiraClient.login();

    // Create a new issue
    const issue = {
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: 'Test Issue',
        description: 'This is a test issue created using the JavaScript Agent with Jira.',
        priority: { name: 'High' }
      }
    };

    // Create the issue in Jira
    const result = await jiraClient.createIssue(issue);

    console.log('Issue created:', result);
  } catch (error) {
    console.error('Error creating issue:', error);
  }
}

// Check if the script is run as the main program
if (require.main === module) {
  main();
}