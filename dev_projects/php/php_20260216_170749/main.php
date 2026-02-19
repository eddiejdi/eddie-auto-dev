<?php

// Importar classes necessárias
use JiraClient\Client;
use JiraClient\Issue;

class PHPAgent {
    private $jiraClient;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl, $username, $password);
    }

    public function trackActivity($issueKey, $activityType, $details) {
        try {
            // Criar um novo issue
            $issue = new Issue([
                'key' => $issueKey,
                'fields' => [
                    'summary' => "Tracking Activity: {$activityType}",
                    'description' => $details,
                    'status' => ['name' => 'In Progress'],
                    'priority' => ['name' => 'High']
                ]
            ]);

            // Adicionar o issue ao Jira
            $this->jiraClient->createIssue($issue);

            return "Activity tracked successfully for issue {$issueKey}";
        } catch (\Exception $e) {
            return "Error tracking activity: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do PHP Agent
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o PHPAgent
        $phpAgent = new PHPAgent($jiraUrl, $username, $password);

        // Exemplo de atividade a ser rastreada
        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $details = "The task was completed successfully.";

        // Rastrear a atividade
        $result = $phpAgent->trackActivity($issueKey, $activityType, $details);

        echo $result;
    }
}

// Executar o script se for CLI
if (__name__ == "__main__") {
    PHPAgent::main();
}