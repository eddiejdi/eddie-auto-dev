<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraTracker {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function createIssue($projectKey, $summary, $description) {
        try {
            $issue = new Issue();
            $issue->setProjectKey($projectKey);
            $issue->setSummary($summary);
            $issue->setDescription($description);

            $this->jiraClient->createIssue($issue);
            return "Issue created successfully";
        } catch (\Exception $e) {
            return "Error creating issue: " . $e->getMessage();
        }
    }

    public function updateIssue($issueKey, $summary, $description) {
        try {
            $issue = new Issue();
            $issue->setKey($issueKey);
            $issue->setSummary($summary);
            $issue->setDescription($description);

            $this->jiraClient->updateIssue($issue);
            return "Issue updated successfully";
        } catch (\Exception $e) {
            return "Error updating issue: " . $e->getMessage();
        }
    }

    public function deleteIssue($issueKey) {
        try {
            $this->jiraClient->deleteIssue($issueKey);
            return "Issue deleted successfully";
        } catch (\Exception $e) {
            return "Error deleting issue: " . $e->getMessage();
        }
    }
}

// Configuração do Jira
$jiraUrl = 'https://your-jira-instance.atlassian.net';
$username = 'your-username';
$password = 'your-password';

// Criar uma instância do JiraTracker
$jiraTracker = new JiraTracker($jiraUrl, $username, $password);

// Exemplo de uso
$projectKey = 'YOUR_PROJECT_KEY';
$summary = 'Test issue';
$description = 'This is a test issue created using PHP Agent with Jira';

echo $jiraTracker->createIssue($projectKey, $summary, $description);