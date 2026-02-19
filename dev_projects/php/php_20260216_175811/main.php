<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use JiraClient\Client;
use JiraClient\Issue;

class JiraIntegration {
    private $client;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        $this->client = new Client($jiraUrl);
        $this->client->login($username, $password);
    }

    public function createIssue($summary, $description) {
        $issueData = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Task']
            ]
        ];

        try {
            $this->issueId = $this->client->issues()->create($issueData)->getId();
            return "Issue created with ID: {$this->issueId}";
        } catch (\Exception $e) {
            return "Error creating issue: " . $e->getMessage();
        }
    }

    public function updateIssueStatus($status) {
        if ($this->issueId === null) {
            throw new Exception("No issue ID set");
        }

        try {
            $updateData = [
                'fields' => ['status' => ['name' => $status]]
            ];

            $this->client->issues()->update($this->issueId, $updateData);
            return "Issue status updated to: {$status}";
        } catch (\Exception $e) {
            return "Error updating issue status: " . $e->getMessage();
        }
    }

    public function deleteIssue() {
        if ($this->issueId === null) {
            throw new Exception("No issue ID set");
        }

        try {
            $this->client->issues()->delete($this->issueId);
            return "Issue deleted";
        } catch (\Exception $e) {
            return "Error deleting issue: " . $e->getMessage();
        }
    }
}

// Exemplo de uso
if (php_sapi_name() === 'cli') {
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    $integration = new JiraIntegration($jiraUrl, $username, $password);

    try {
        echo $integration->createIssue('Task 1', 'This is the first task.');
        echo $integration->updateIssueStatus('In Progress');
        echo $integration->deleteIssue();
    } catch (\Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}