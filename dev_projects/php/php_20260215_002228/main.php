<?php

// Import required libraries
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraIntegration {
    private $jiraApiUrl;
    private $username;
    private $password;
    private $projectKey;

    public function __construct($jiraApiUrl, $username, $password, $projectKey) {
        $this->jiraApiUrl = $jiraApiUrl;
        $this->username = $username;
        $this->password = $password;
        $this->projectKey = $projectKey;
    }

    public function createIssue($issueData) {
        try {
            $agent = new Agent([
                'url' => $this->jiraApiUrl,
                'auth' => [
                    'username' => $this->username,
                    'password' => $this->password
                ]
            ]);

            $response = $agent->post('/rest/api/2/issue', [
                'json' => $issueData
            ]);

            return json_decode($response, true);
        } catch (AgentException $e) {
            throw new Exception("Failed to create issue: " . $e->getMessage());
        }
    }

    public function updateIssue($issueKey, $updateData) {
        try {
            $agent = new Agent([
                'url' => $this->jiraApiUrl,
                'auth' => [
                    'username' => $this->username,
                    'password' => $this->password
                ]
            ]);

            $response = $agent->put("/rest/api/2/issue/{$issueKey}", [
                'json' => $updateData
            ]);

            return json_decode($response, true);
        } catch (AgentException $e) {
            throw new Exception("Failed to update issue: " . $e->getMessage());
        }
    }

    public function getIssue($issueKey) {
        try {
            $agent = new Agent([
                'url' => $this->jiraApiUrl,
                'auth' => [
                    'username' => $this->username,
                    'password' => $this->password
                ]
            ]);

            $response = $agent->get("/rest/api/2/issue/{$issueKey}");

            return json_decode($response, true);
        } catch (AgentException $e) {
            throw new Exception("Failed to get issue: " . $e->getMessage());
        }
    }

    public function deleteIssue($issueKey) {
        try {
            $agent = new Agent([
                'url' => $this->jiraApiUrl,
                'auth' => [
                    'username' => $this->username,
                    'password' => $this->password
                ]
            ]);

            $response = $agent->delete("/rest/api/2/issue/{$issueKey}");

            return json_decode($response, true);
        } catch (AgentException $e) {
            throw new Exception("Failed to delete issue: " . $e->getMessage());
        }
    }
}

function main() {
    // Example usage
    $jiraIntegration = new JiraIntegration('https://your-jira-instance.com', 'your-username', 'your-password', 'YOUR_PROJECT_KEY');

    $issueData = [
        'fields' => [
            'project' => ['key' => $jiraIntegration->projectKey],
            'summary' => 'Example issue',
            'description' => 'This is an example issue created using PHP Agent and Jira API.',
            'issuetype' => ['name' => 'Bug']
        ]
    ];

    try {
        $issue = $jiraIntegration->createIssue($issueData);
        echo "Issue created successfully: " . json_encode($issue, JSON_PRETTY_PRINT) . "\n";
    } catch (Exception $e) {
        echo "Error creating issue: " . $e->getMessage() . "\n";
    }
}

if (__name__ == "__main__") {
    main();
}