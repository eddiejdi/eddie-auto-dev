<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\JiraClient;
use PhpAgent\EventLogger;

class Scrum15 {
    private $jiraClient;
    private $eventLogger;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
        $this->eventLogger = new EventLogger();
    }

    public function monitorActivities() {
        try {
            // Listar todas as atividades
            $issues = $this->jiraClient->getIssues();

            foreach ($issues as $issue) {
                $this->logEvent("Issue {$issue['key']} - Status: {$issue['fields']['status']['name']}");
            }
        } catch (Exception $e) {
            $this->logEvent("Error monitoring activities: " . $e->getMessage());
        }
    }

    public function registerEvents() {
        try {
            // Registrar eventos
            $events = [
                ['title' => 'Task Completed', 'description' => 'A task was completed'],
                ['title' => 'Bug Fixed', 'description' => 'A bug was fixed']
            ];

            foreach ($events as $event) {
                $this->logEvent("Event: {$event['title']} - Description: {$event['description']}");
            }
        } catch (Exception $e) {
            $this->logEvent("Error registering events: " . $e->getMessage());
        }
    }

    private function logEvent($message) {
        $this->eventLogger->log($message);
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Monitorar atividades
        $scrum15->monitorActivities();

        // Registrar eventos
        $scrum15->registerEvents();
    }
}

// Executar o programa
Scrum15::main();