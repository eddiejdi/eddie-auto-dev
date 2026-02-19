<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class JiraAgent {
    private $client;

    public function __construct($url, $username, $password) {
        $this->client = new Client([
            'base_url' => $url,
            'auth' => [$username, $password]
        ]);
    }

    public function trackActivity($issueKey, $activityType, $details) {
        try {
            // Criar o issue
            $issue = new Issue([
                'key' => $issueKey,
                'fields' => [
                    'summary' => "Tracking Activity - {$activityType}",
                    'description' => $details,
                    'status' => [
                        'name' => 'In Progress'
                    ]
                ]
            ]);

            // Adicionar o issue ao Jira
            $this->client->issues()->create($issue);

            echo "Activity tracked successfully.\n";
        } catch (Exception $e) {
            echo "Error tracking activity: {$e->getMessage()}\n";
        }
    }

    public static function main() {
        // Configurações do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o JiraAgent
        $jiraAgent = new JiraAgent($url, $username, $password);

        // Exemplo de uso da função trackActivity
        $issueKey = 'ABC123';
        $activityType = 'Bug Fix';
        $details = 'Fixed a critical bug in the application';

        $jiraAgent->trackActivity($issueKey, $activityType, $details);
    }
}

// Executar o script principal
JiraAgent::main();