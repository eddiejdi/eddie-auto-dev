<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client;
use PHPAgent\PHPAgent;

class Scrum15 {
    private $jiraClient;
    private $phpAgent;

    public function __construct($jiraUrl, $username, $password) {
        // Inicializar o cliente de Jira
        $this->jiraClient = new Client($jiraUrl, $username, $password);

        // Inicializar o PHP Agent
        $this->phpAgent = new PHPAgent();
    }

    public function trackActivity($issueKey, $activity) {
        try {
            // Criar um novo issue ou atualizar um existente
            $issue = $this->jiraClient->issues()->create([
                'fields' => [
                    'summary' => "New Activity: {$activity}",
                    'description' => "Activity tracked by PHP Agent",
                    'issuetype' => ['name' => 'Task'],
                    'project' => ['key' => 'YOUR_PROJECT_KEY']
                ]
            ]);

            // Adicionar o PHP Agent ao issue
            $this->phpAgent->addIssue($issue);

            echo "Activity tracked successfully with issue key: {$issueKey}\n";
        } catch (\Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Configuração do PHP Agent
        $phpAgentConfig = [
            'name' => 'PHP Agent',
            'version' => '1.0.0',
            'description' => 'Tracking activities with PHP Agent'
        ];

        // Instanciar o Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Simulação de atividade
        $issueKey = 'ABC-123';
        $activity = 'Executing a PHP script';

        // Tracar a atividade
        $scrum15->trackActivity($issueKey, $activity);
    }
}

// Executar o programa como um script CLI
if (__name__ == "__main__") {
    Scrum15::main();
}