<?php

// Import necessary libraries and classes
require 'vendor/autoload.php';

use JiraClient\Client;
use JiraClient\Issue;

// Define the main function
function main() {
    // Initialize the Jira client
    $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-api-token');

    // Create a new issue
    $issue = new Issue(
        'My New Issue',
        'This is a test issue.',
        '10100'
    );

    // Add custom fields to the issue
    $issue->addCustomField('customfield_12345', 'Value 1');
    $issue->addCustomField('customfield_67890', 'Value 2');

    // Create the issue in Jira
    $createdIssue = $client->createIssue($issue);

    echo "Issue created: {$createdIssue->getKey()}\n";

    // Fetch and print all issues from Jira
    $issues = $client->getIssues();

    foreach ($issues as $issue) {
        echo "Issue ID: {$issue->getId()}, Summary: {$issue->getSummary()}\n";
    }
}

// Execute the main function if this script is run directly
if (__name__ == "__main__") {
    main();
}