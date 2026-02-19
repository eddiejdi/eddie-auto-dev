<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Jira;

class Scrum15 {
    private $agent;
    private $jira;

    public function __construct() {
        // Configurar PHP Agent
        $this->agent = new Agent();
        $this->agent->setConfig([
            'token' => 'your_php_agent_token',
            'url' => 'http://localhost:8080'
        ]);

        // Configurar Jira
        $this->jira = new Jira();
        $this->jira->setConfig([
            'baseUrl' => 'https://your-jira-instance.atlassian.net',
            'username' => 'your_username',
            'password' => 'your_password'
        ]);
    }

    public function monitorarAtividades() {
        // Simular atividade em PHP
        $this->agent->log('PHP Agent is running');

        // Monitorar atividades no Jira
        try {
            $issue = $this->jira->createIssue([
                'summary' => 'PHP Agent Activity',
                'description' => 'This issue is created by the PHP Agent.',
                'projectKey' => 'YOUR_PROJECT_KEY'
            ]);

            echo "Issue created: {$issue['key']}\n";
        } catch (\Exception $e) {
            echo "Error creating issue: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        $scrum15 = new Scrum15();
        $scrum15->monitorarAtividades();
    }
}

if (__name__ == "__main__") {
    Scrum15::main();
}