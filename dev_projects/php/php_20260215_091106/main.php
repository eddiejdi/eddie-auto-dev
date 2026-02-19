<?php

// Importar classes necessárias
use Jira\JiraClient;
use Jira\Entity\Issue;

class PHPAgent {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            // Criar um novo issue
            $issue = new Issue();
            $issue->setSummary("Tracking Activity: " . $activityDescription);
            $issue->setStatusId(10000); // Status em progresso

            // Adicionar atividade ao issue
            $this->jiraClient->addComment($issueKey, $activityDescription);

            return "Activity tracked successfully.";
        } catch (Exception $e) {
            return "Error tracking activity: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do PHP Agent
        $url = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar um objeto PHPAgent
        $phpAgent = new PHPAgent($url, $username, $password);

        // Exemplo de uso
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in successfully.';
        echo $phpAgent->trackActivity($issueKey, $activityDescription);
    }
}

// Executar o script se for CLI
if (__name__ == "__main__") {
    PHPAgent::main();
}