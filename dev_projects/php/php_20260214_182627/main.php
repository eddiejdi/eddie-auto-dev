<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraScrum15 {

    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
    }

    public function setIssueId($issueId) {
        $this->issueId = $issueId;
    }

    public function trackActivity() {
        try {
            // Obter o issue do Jira
            $issue = $this->jiraClient->getIssue($this->issueId);

            // Logar a atividade no console
            echo "Tracking issue {$issue->getKey()}:\n";
            echo "Status: {$issue->getStatus()->getName()}\n";
            echo "Assignee: {$issue->getAssignee()->getName()}\n";

            // Simular atualização do status (por exemplo, via API)
            $newStatus = 'In Progress';
            $this->jiraClient->updateIssueStatus($this->issueId, $newStatus);

            // Logar a mudança de status no console
            echo "Updated status to: {$newStatus}\n";

        } catch (\Exception $e) {
            echo "Error tracking issue: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if (count($argv) != 4) {
            echo "Usage: php jira_scrum15.php <jira_url> <username> <password> <issue_id>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];
        $issueId = $argv[4];

        $jiraScrum15 = new JiraScrum15($jiraUrl, $username, $password);
        $jiraScrum15->setIssueId($issueId);
        $jiraScrum15->trackActivity();
    }
}

if (__name__ == "__main__") {
    JiraScrum15::main($_SERVER['argv']);
}