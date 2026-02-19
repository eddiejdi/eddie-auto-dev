<?php

// Import necessary libraries
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Api\ProjectApi;

class PhpAgent {
    private $client;
    private $projectApi;

    public function __construct($jiraUrl, $username, $password) {
        // Initialize Jira client
        $this->client = new Client([
            'url' => $jiraUrl,
            'auth' => [$username, $password]
        ]);

        // Initialize Project API
        $this->projectApi = new ProjectApi($this->client);
    }

    public function trackTask($projectId, $taskKey, $status) {
        try {
            // Update task status
            $this->projectApi->updateIssueStatus($projectId, $taskKey, [
                'fields' => [
                    'status' => [
                        'name' => $status
                    ]
                ]
            ]);

            echo "Task updated successfully.\n";
        } catch (\Exception $e) {
            echo "Error updating task: " . $e->getMessage() . "\n";
        }
    }

    public function trackProject($projectId, $status) {
        try {
            // Update project status
            $this->projectApi->updateProjectStatus($projectId, [
                'fields' => [
                    'status' => [
                        'name' => $status
                    ]
                ]
            ]);

            echo "Project updated successfully.\n";
        } catch (\Exception $e) {
            echo "Error updating project: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if (count($argv) < 5) {
            echo "Usage: php php-agent.php <jira-url> <username> <password> <project-id> <task-key> <status>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];
        $projectId = $argv[4];
        $taskKey = $argv[5];
        $status = $argv[6];

        try {
            $phpAgent = new PhpAgent($jiraUrl, $username, $password);
            $phpAgent->trackTask($projectId, $taskKey, $status);
        } catch (\Exception $e) {
            echo "Error tracking task: " . $e->getMessage() . "\n";
        }
    }
}

if (__name__ == "__main__") {
    PhpAgent::main($_SERVER['argv']);
}