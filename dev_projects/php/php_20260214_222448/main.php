<?php

// Import necessary libraries
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Report;

// Function to create a Jira client
function createJiraClient($url, $username, $password) {
    return new \PhpAgent\Client($url, $username, $password);
}

// Function to track an activity in Jira
function trackActivity($jiraClient, $issueKey, $activityDescription) {
    try {
        $report = new Report();
        $report->add('Issue Key', $issueKey);
        $report->add('Activity Description', $activityDescription);

        $agent = Agent::getInstance();
        $agent->log($report);

        return true;
    } catch (\Exception $e) {
        echo "Error tracking activity: " . $e->getMessage() . "\n";
        return false;
    }
}

// Main function to integrate PHP Agent with Jira
function main() {
    // Replace these values with your actual Jira credentials and issue key
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $jiraUsername = 'your-username';
    $jiraPassword = 'your-password';
    $issueKey = 'YOUR-ISSUE-Key';

    // Create a Jira client
    $jiraClient = createJiraClient($jiraUrl, $jiraUsername, $jiraPassword);

    // Track an activity in Jira
    if (trackActivity($jiraClient, $issueKey, 'This is a test activity')) {
        echo "Activity tracked successfully.\n";
    }
}

// Check if the script is executed as the main program
if (__name__ == "__main__") {
    main();
}