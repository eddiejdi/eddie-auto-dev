// Import necessary libraries and modules
const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Define the main function to run the application
async function main() {
  try {
    // Create a new instance of the Jira client
    const jiraClient = new JiraClient({
      protocol: 'https',
      hostname: 'your-jira-hostname.com',
      port: 443,
      username: 'your-username',
      password: 'your-password'
    });

    // Define the activity tracking function
    async function trackActivity(issueKey, activity) {
      const response = await jiraClient.request({
        method: 'POST',
        url: `/rest/api/2/issue/${issueKey}/comment`,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          comment: {
            author: {
              name: 'Your Name'
            },
            body: activity
          }
        })
      });

      console.log(`Activity tracked for issue ${issueKey}:`, response.data);
    }

    // Example usage of the trackActivity function
    const issueKey = 'ABC-123';
    const activity = 'This is a test activity.';
    await trackActivity(issueKey, activity);

    // Define the alerting function
    async function alertIssue(issueKey) {
      const response = await jiraClient.request({
        method: 'POST',
        url: `/rest/api/2/issue/${issueKey}/worklog`,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          comment: {
            author: {
              name: 'Your Name'
            },
            body: 'Alerting issue for work log.'
          }
        })
      });

      console.log(`Issue alerted for ${issueKey}:`, response.data);
    }

    // Example usage of the alertIssue function
    const issueKey = 'ABC-123';
    await alertIssue(issueKey);

  } catch (error) {
    console.error('Error:', error);
  }
}

// Execute the main function if this script is run directly
if (require.main === module) {
  main();
}