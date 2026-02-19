<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;

class JiraIntegration {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            $response = $this->jiraClient->createIssueComment($issueKey, $activityDescription);
            return "Activity tracked successfully: " . json_encode($response);
        } catch (Exception $e) {
            return "Error tracking activity: " . $e->getMessage();
        }
    }

    public function main() {
        // Exemplo de uso da classe
        $jiraIntegration = new JiraIntegration('https://your-jira-instance.com', 'your-username', 'your-password');
        $issueKey = 'ABC-123';
        $activityDescription = 'This is a test activity';

        echo $jiraIntegration->trackActivity($issueKey, $activityDescription);
    }
}

if (__name__ == "__main__") {
    JiraIntegration::main();
}