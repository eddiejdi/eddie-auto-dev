<?php

// Importar classes necessárias
use Jira\Client;
use Jira\Issue;

class PHPAgent {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        // Configurar o cliente do Jira
        $this->jiraClient = new Client($url, $username, $password);
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            // Criar um novo issue
            $issue = new Issue();
            $issue->setKey($issueKey);
            $issue->setDescription($activityDescription);

            // Adicionar o issue ao Jira
            $this->jiraClient->issues()->create($issue);

            echo "Activity tracked successfully for issue {$issueKey}.\n";
        } catch (\Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        // Configuração do PHP Agent
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância do PHPAgent
        $phpAgent = new PHPAgent($url, $username, $password);

        // Exemplo de atividade a ser registrada
        $issueKey = 'ABC-123';
        $activityDescription = "User logged in from IP address 192.168.1.1";

        // Registrar a atividade no Jira
        $phpAgent->trackActivity($issueKey, $activityDescription);
    }
}

// Executar o script como um programa de linha de comando
if (__name__ == "__main__") {
    PHPAgent::main();
}