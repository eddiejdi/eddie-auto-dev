<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;
use Jira\Project;

class Scrum15 {
    private $jiraClient;
    private $projectKey;

    public function __construct($jiraUrl, $username, $password, $projectKey) {
        $this->jiraClient = new Client($jiraUrl);
        $this->jiraClient->login($username, $password);
        $this->projectKey = $projectKey;
    }

    public function monitorarProcessos() {
        $issueList = $this->jiraClient->getProjectIssues($this->projectKey);

        foreach ($issueList as $issue) {
            $status = $issue->getStatus()->getName();
            echo "Issue {$issue->getKey()} - Status: {$status}\n";
        }
    }

    public function gerenciarRelatorios() {
        // Implementar aqui a lógica para gerenciamento de relatórios
        echo "Gerenciando relatórios...\n";
    }

    public static function main($argv) {
        if (count($argv) !== 5) {
            echo "Usage: php scrum15.php <jira-url> <username> <password> <project-key>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];
        $projectKey = $argv[4];

        $scrum15 = new Scrum15($jiraUrl, $username, $password, $projectKey);
        $scrum15->monitorarProcessos();
        $scrum15->gerenciarRelatorios();
    }
}

if (__name__ == "__main__") {
    Scrum15::main($_SERVER['argv']);
}