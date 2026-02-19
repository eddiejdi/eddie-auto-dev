<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira;
use PhpAgent\Exception\ConnectionException;

class JiraIntegration {
    private $jira;

    public function __construct($url, $username, $password) {
        try {
            $this->jira = new Jira($url, $username, $password);
        } catch (ConnectionException $e) {
            echo "Erro ao conectar com o Jira: " . $e->getMessage();
            exit;
        }
    }

    public function trackActivity($issueKey, $activityType, $description) {
        try {
            $this->jira->addComment($issueKey, $activityType, $description);
            echo "Atividade registrada com sucesso.";
        } catch (Exception $e) {
            echo "Erro ao registrar atividade: " . $e->getMessage();
        }
    }

    public static function main() {
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $jiraIntegration = new JiraIntegration($url, $username, $password);

        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $description = 'The task was completed successfully';

        $jiraIntegration->trackActivity($issueKey, $activityType, $description);
    }
}

// Executar o script como um programa standalone
if (__name__ == "__main__") {
    JiraIntegration::main();
}