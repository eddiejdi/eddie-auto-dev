<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issue;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new Client($url);
        $this->issue = new Issue();
    }

    public function trackActivity($activityName) {
        try {
            $this->issue->setSummary("Tracking: " . $activityName);
            $this->issue->setDescription("This is a tracking issue for " . $activityName);

            // Adicionar o issue ao Jira
            $this->jiraClient->createIssue($this->issue);

            echo "Activity tracked successfully.\n";
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        // Configuração do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe Scrum15
        $scrum15 = new Scrum15($url, $username, $password);

        // Exemplo de atividade a ser trackeada
        $activityName = "Implement PHP Agent with Jira";

        // Chamar o método para trackar a atividade
        $scrum15->trackActivity($activityName);
    }
}

// Executar o script em modo CLI
if (__name__ == "__main__") {
    Scrum15::main();
}