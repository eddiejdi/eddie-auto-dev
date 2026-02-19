<?php

// Importar classes necessárias
use JiraClient\Client;
use JiraClient\Issue;

class PHPAgent {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new Client($url, $username, $password);
    }

    public function createIssue($issueData) {
        try {
            $issue = new Issue();
            foreach ($issueData as $key => $value) {
                $issue->$key = $value;
            }
            $this->jiraClient->createIssue($issue);
            return "Issue created successfully";
        } catch (\Exception $e) {
            return "Error creating issue: " . $e->getMessage();
        }
    }

    public function updateIssue($issueId, $issueData) {
        try {
            $issue = new Issue();
            foreach ($issueData as $key => $value) {
                $issue->$key = $value;
            }
            $this->jiraClient->updateIssue($issueId, $issue);
            return "Issue updated successfully";
        } catch (\Exception $e) {
            return "Error updating issue: " . $e->getMessage();
        }
    }

    public function deleteIssue($issueId) {
        try {
            $this->jiraClient->deleteIssue($issueId);
            return "Issue deleted successfully";
        } catch (\Exception $e) {
            return "Error deleting issue: " . $e->getMessage();
        }
    }
}

// Exemplo de uso
if (php_sapi_name() === 'cli') {
    require_once 'PHPAgent.php';

    $jiraClient = new PHPAgent('https://your-jira-url.com', 'username', 'password');
    $issueData = [
        'summary' => 'Test Issue',
        'description' => 'This is a test issue created by the PHP Agent.',
        'priority' => 'High',
        'assignee' => 'user123'
    ];

    try {
        echo $jiraClient->createIssue($issueData);
    } catch (\Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}