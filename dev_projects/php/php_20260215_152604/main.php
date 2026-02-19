<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;
use PhpAgent\Exception\ConnectionException;

class Scrum15 {
    private $jiraUrl;
    private $jiraUsername;
    private $jiraPassword;
    private $agent;

    public function __construct($jiraUrl, $jiraUsername, $jiraPassword) {
        $this->jiraUrl = $jiraUrl;
        $this->jiraUsername = $jiraUsername;
        $this->jiraPassword = $jiraPassword;
        $this->agent = new Agent();
    }

    public function connectToJira() {
        try {
            $this->agent->connect($this->jiraUrl, $this->jiraUsername, $this->jiraPassword);
            echo "Connected to Jira successfully.\n";
        } catch (AgentException | ConnectionException $e) {
            echo "Failed to connect to Jira: " . $e->getMessage() . "\n";
        }
    }

    public function trackActivity($activityName, $description) {
        try {
            $issue = $this->agent->createIssue([
                'summary' => $activityName,
                'description' => $description,
                'project' => [
                    'key' => 'YOUR_PROJECT_KEY'
                ],
                'assignee' => [
                    'name' => 'YOUR_USERNAME'
                ]
            ]);

            echo "Activity tracked successfully: " . $issue->getKey() . "\n";
        } catch (AgentException | ConnectionException $e) {
            echo "Failed to track activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';

        $scrum15 = new Scrum15($jiraUrl, $jiraUsername, $jiraPassword);

        try {
            $scrum15->connectToJira();
            $scrum15->trackActivity('New Task', 'Create a new task in the project.');
        } catch (Exception $e) {
            echo "An error occurred: " . $e->getMessage() . "\n";
        }
    }
}

if (__name__ == "__main__") {
    Scrum15::main();
}