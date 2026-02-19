<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Model\Issue;

class Scrum15 {
    private $jiraClient;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl, $username, $password);
    }

    public function trackActivity($issueKey, $status) {
        try {
            // Obter o issue do Jira
            $issue = $this->jiraClient->getIssue($issueKey);

            // Atualizar o status do issue
            $issue->setStatus(new Issue\Status($status));

            // Salvar as alterações no Jira
            $this->jiraClient->updateIssue($issue);
        } catch (\Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        $scrum15 = new Scrum15('https://your-jira-url.com', 'username', 'password');

        // Exemplo de uso
        $issueKey = 'SCM-001';
        $status = 'In Progress';

        $scrum15->trackActivity($issueKey, $status);
    }
}

if (__name__ == "__main__") {
    Scrum15::main();
}