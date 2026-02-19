// Importing necessary modules and packages
const axios = require('axios');
const { exec } = require('child_process');

// Main function to run the integration process
async function main() {
  try {
    // Step 1: Install JavaScript Agent on your server
    console.log("Installing JavaScript Agent...");
    await installJavaScriptAgent();

    // Step 2: Configure JavaScript Agent for capturing relevant data
    console.log("Configuring JavaScript Agent...");
    await configureJavaScriptAgent();

    // Step 3: Integrate with Jira to send information about activities
    console.log("Integrating with Jira...");
    await integrateWithJira();
  } catch (error) {
    console.error("An error occurred during the integration process:", error);
  }
}

// Function to install JavaScript Agent on the server
async function installJavaScriptAgent() {
  try {
    // Execute a command to install the JavaScript Agent on your server
    exec('npm install javascript-agent', (err, stdout, stderr) => {
      if (err) {
        console.error("Error installing JavaScript Agent:", err);
      } else {
        console.log("JavaScript Agent installed successfully.");
      }
    });
  } catch (error) {
    throw new Error("Failed to install JavaScript Agent.");
  }
}

// Function to configure JavaScript Agent for capturing relevant data
async function configureJavaScriptAgent() {
  try {
    // Execute a command to configure the JavaScript Agent on your server
    exec('npm run config', (err, stdout, stderr) => {
      if (err) {
        console.error("Error configuring JavaScript Agent:", err);
      } else {
        console.log("JavaScript Agent configured successfully.");
      }
    });
  } catch (error) {
    throw new Error("Failed to configure JavaScript Agent.");
  }
}

// Function to integrate with Jira to send information about activities
async function integrateWithJira() {
  try {
    // Execute a command to send data to Jira using the JavaScript Agent
    exec('npm run send', (err, stdout, stderr) => {
      if (err) {
        console.error("Error sending data to Jira:", err);
      } else {
        console.log("Data sent successfully to Jira.");
      }
    });
  } catch (error) {
    throw new Error("Failed to integrate with Jira.");
  }
}

// Execute the main function
main();