<?php

// Import necessary libraries
require 'vendor/autoload.php';

// Define the PHP Agent class
class PHPAgent {
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
    }

    // Function to log an activity
    public function logActivity($issueKey, $activityType, $description) {
        try {
            // Create a cURL session
            $ch = curl_init();

            // Set the URL for the Jira API
            curl_setopt($ch, CURLOPT_URL, $this->jiraUrl . '/rest/api/2/issue/' . $issueKey . '/comment');

            // Set the request headers
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                'Content-Type: application/json',
                'Authorization: Basic ' . base64_encode($this->username . ':' . $this->password)
            ]);

            // Set the POST data
            $data = json_encode([
                'body' => [
                    'type' => 'doc',
                    'content' => [
                        'paragraph' => [
                            'text' => $description
                        ]
                    ]
                ]
            ]);

            curl_setopt($ch, CURLOPT_POSTFIELDS, $data);

            // Execute the cURL session
            $response = curl_exec($ch);

            // Check for errors
            if (curl_errno($ch)) {
                throw new Exception('Error: ' . curl_error($ch));
            }

            // Close the cURL session
            curl_close($ch);

            return true;
        } catch (Exception $e) {
            echo "Error logging activity: " . $e->getMessage();
            return false;
        }
    }
}

// Example usage
if (__name__ == "__main__") {
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    $agent = new PHPAgent($jiraUrl, $username, $password);

    $issueKey = 'ABC-123';
    $activityType = 'Task Completed';
    $description = 'The task was completed successfully';

    if ($agent->logActivity($issueKey, $activityType, $description)) {
        echo "Activity logged successfully.";
    }
}