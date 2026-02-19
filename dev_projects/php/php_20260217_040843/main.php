<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class PhpAgent {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl);
        $this->jiraClient->login($username, $password);
    }

    public function createIssue($summary, $description) {
        $issueData = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        try {
            $this->issueId = $this->jiraClient->createIssue($issueData);
            echo "Issue created with ID: {$this->issueId}\n";
        } catch (\Exception $e) {
            echo "Error creating issue: " . $e->getMessage() . "\n";
        }
    }

    public function logEvent($eventName, $eventDescription) {
        try {
            $this->jiraClient->logEvent($this->issueId, $eventName, $eventDescription);
            echo "Log event created for issue {$this->issueId}\n";
        } catch (\Exception $e) {
            echo "Error creating log event: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if (count($argv) != 5) {
            echo "Usage: php php_agent.php <jira_url> <username> <password> <summary> <description>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];
        $summary = $argv[4];
        $description = $argv[5];

        $phpAgent = new PhpAgent($jiraUrl, $username, $password);
        $phpAgent->createIssue($summary, $description);
        $phpAgent->logEvent('PHP Agent Log', 'This is a log event from the PHP Agent.');
    }
}

if (__name__ == "__main__") {
    PhpAgent::main($_SERVER['argv']);
}