const axios = require('axios');
const { createLogger } = require('winston');

// Setting up logger
const logger = createLogger({
  level: 'info',
  format: 'json',
});

// Class to represent a Jira issue
class JiraIssue {
  constructor(issueId, summary) {
    this.issueId = issueId;
    this.summary = summary;
  }
}

// Function to send an event to Jira using JavaScript Agent
async function sendEventToJira(eventData) {
  try {
    const response = await axios.post(
      'https://your-jira-instance.atlassian.net/rest/api/2/issue/{issueId}/comment',
      eventData,
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${process.env.JIRA_API_TOKEN}`,
        },
      }
    );

    logger.info(`Event sent to Jira successfully. Response: ${response.data}`);
  } catch (error) {
    logger.error(`Error sending event to Jira: ${error.message}`);
  }
}

// Main function to run the script
async function main() {
  try {
    // Create a new Jira issue
    const issue = new JiraIssue('12345', 'This is a test issue');

    // Data for the event
    const eventData = {
      body: `A new task has been created in Jira: ${issue.summary}`,
      visibility: {
        type: 'global',
      },
    };

    // Send the event to Jira
    await sendEventToJira(eventData);

    console.log('Script executed successfully.');
  } catch (error) {
    logger.error(`Error executing script: ${error.message}`);
  }
}

// Check if the script is run directly and execute main function
if (require.main === module) {
  main();
}