<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraIntegration {
    private $agent;
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
        $this->agent = new Agent();
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            // Autenticar o usuário
            $this->agent->authenticate($this->jiraUrl, $this->username, $this->password);

            // Criar a atividade no Jira
            $issue = $this->agent->createIssue($this->jiraUrl, [
                'fields' => [
                    'project' => ['key' => 'YOUR_PROJECT_KEY'],
                    'summary' => 'New Activity',
                    'description' => $activityDescription,
                    'issuetype' => ['name' => 'Task']
                ]
            ]);

            echo "Activity tracked successfully: " . $issue['id'];
        } catch (AgentException $e) {
            echo "Error tracking activity: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instancia da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: Tracar uma atividade em um issue
        $issueKey = 'ABC-123';
        $activityDescription = 'This is a test activity.';
        $integration->trackActivity($issueKey, $activityDescription);
    }
}

// Executar o script como um programa standalone
if (__name__ == "__main__") {
    JiraIntegration::main();
}