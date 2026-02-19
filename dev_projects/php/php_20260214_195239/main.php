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

    // Method to track an issue
    public function trackIssue($issueKey, $status) {
        $url = $this->jiraUrl . '/rest/api/3/issue/' . $issueKey . '/transitions';
        $headers = [
            'Content-Type: application/json',
            'Authorization: Basic ' . base64_encode($this->username . ':' . $this->password)
        ];

        $data = json_encode([
            "transition" => [
                "id" => $status
            ]
        ]);

        try {
            $response = curl_init();
            curl_setopt($response, CURLOPT_URL, $url);
            curl_setopt($response, CURLOPT_POST, true);
            curl_setopt($response, CURLOPT_POSTFIELDS, $data);
            curl_setopt($response, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($response, CURLOPT_HTTPHEADER, $headers);

            $result = json_decode(curl_exec($response), true);
            if (isset($result['errorMessages'])) {
                throw new Exception("Error tracking issue: " . implode(', ', $result['errorMessages']));
            }

            return $result;
        } catch (Exception $e) {
            error_log("PHP Agent Error: " . $e->getMessage());
            return false;
        } finally {
            curl_close($response);
        }
    }
}

// Example usage
if (__name__ == "__main__") {
    $jiraUrl = 'https://your-jira-instance.com';
    $username = 'your-username';
    $password = 'your-password';

    $agent = new PHPAgent($jiraUrl, $username, $password);
    $issueKey = 'ABC123';
    $status = 10; // Assuming status ID for 'In Progress'

    try {
        $result = $agent->trackIssue($issueKey, $status);
        print_r($result);
    } catch (Exception $e) {
        echo "Failed to track issue: " . $e->getMessage();
    }
}