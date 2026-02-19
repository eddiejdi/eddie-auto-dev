// Importing necessary libraries and modules
const axios = require('axios');
const { JiraClient } = require('@atlassian/node-jira-client');

// Main function to run the script
async function main() {
  try {
    // Initialize Jira client
    const jiraClient = new JiraClient({
      auth: {
        username: 'your_username',
        password: 'your_password'
      },
      options: {
        host: 'https://your_jira_host'
      }
    });

    // Function to create a new issue in Jira
    async function createIssue(title, description) {
      const issue = await jiraClient.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description,
          issuetype: { name: 'Task' }
        }
      });

      console.log(`Issue created with ID: ${issue.id}`);
    }

    // Function to update an existing issue in Jira
    async function updateIssue(issueId, title, description) {
      const updatedIssue = await jiraClient.updateIssue({
        id: issueId,
        fields: {
          summary: title,
          description: description
        }
      });

      console.log(`Issue updated with ID: ${updatedIssue.id}`);
    }

    // Function to delete an existing issue in Jira
    async function deleteIssue(issueId) {
      const deletedIssue = await jiraClient.deleteIssue({
        id: issueId
      });

      console.log(`Issue deleted with ID: ${deletedIssue.id}`);
    }

    // Example usage of the functions
    await createIssue('New Task', 'This is a new task description');
    await updateIssue('1234567890', 'Updated Task', 'This is an updated task description');
    await deleteIssue('1234567890');

  } catch (error) {
    console.error('Error:', error);
  }
}

// Execute the main function
if (require.main === module) {
  main();
}