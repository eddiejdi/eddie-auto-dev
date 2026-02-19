<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl, $username, $password);
    }

    public function setIssueId($issueId) {
        $this->issueId = $issueId;
    }

    public function trackActivity() {
        try {
            // Obter a tarefa específica
            $issue = $this->jiraClient->getIssueById($this->issueId);

            // Monitorar atividades da tarefa
            echo "Tracking activity for issue {$issue->getKey()}:\n";
            while ($issue->hasNext()) {
                $activity = $issue->next();
                echo "- {$activity->getName()}\n";
            }
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if (count($argv) != 4) {
            echo "Usage: php scrum15.php <jira-url> <username> <password> <issue-id>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];
        $issueId = $argv[4];

        $scrum15 = new Scrum15($jiraUrl, $username, $password);
        $scrum15->setIssueId($issueId);
        $scrum15->trackActivity();
    }
}

if (defined('__DIR__')) {
    require __DIR__ . '/vendor/autoload.php';
}