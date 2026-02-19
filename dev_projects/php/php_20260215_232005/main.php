<?php

// Import necessary libraries
require 'vendor/autoload.php';

// Define the JiraClient class to interact with Jira API
class JiraClient {
    private $url;
    private $username;
    private $password;

    public function __construct($url, $username, $password) {
        $this->url = $url;
        $this->username = $username;
        $this->password = $password;
    }

    public function createIssue($projectKey, $summary, $description) {
        // Prepare the request body
        $body = [
            'fields' => [
                'project' => ['key' => $projectKey],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Task']
            ]
        ];

        // Send a POST request to create the issue
        $response = $this->sendRequest('POST', '/rest/api/2/issue', json_encode($body));

        if ($response['status'] === 201) {
            return $response['id'];
        } else {
            throw new Exception("Failed to create issue: " . $response['error']);
        }
    }

    private function sendRequest($method, $endpoint, $body = null) {
        // Set up cURL options
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $this->url . $endpoint);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                'Content-Type: application/json',
                'Authorization: Basic ' . base64_encode("$this->username:$this->password")
            ]);
        }

        // Execute the cURL request
        $response = curl_exec($ch);
        curl_close($ch);

        // Decode JSON response
        return json_decode($response, true);
    }
}

// Example usage of JiraClient
if (php_sapi_name() === 'cli') {
    $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    try {
        $issueId = $jira->createIssue('YOUR_PROJECT_KEY', 'Task Summary', 'This is a test task.');
        echo "Issue created with ID: $issueId\n";
    } catch (Exception $e) {
        echo "Error creating issue: " . $e->getMessage() . "\n";
    }
}