<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Exception as JiraException;

class Scrum15 {
    private $jiraClient;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl, $username, $password);
    }

    public function monitorarAtividades() {
        try {
            $issues = $this->jiraClient->searchIssues();
            foreach ($issues as $issue) {
                echo "Issue ID: {$issue['id']}, Summary: {$issue['fields']['summary']} \n";
            }
        } catch (JiraException $e) {
            echo "Error monitoring issues: " . $e->getMessage() . "\n";
        }
    }

    public function registrarEventos($eventName, $eventData) {
        try {
            $this->jiraClient->createIssue([
                'fields' => [
                    'project' => ['key' => 'YOUR_PROJECT_KEY'],
                    'summary' => $eventName,
                    'description' => json_encode($eventData),
                    'issuetype' => ['name' => 'Task']
                ]
            ]);
            echo "Event registered successfully.\n";
        } catch (JiraException $e) {
            echo "Error registering event: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if ($argc !== 4) {
            echo "Usage: php scrum15.php <jira-url> <username> <password>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];

        try {
            $scrum15 = new Scrum15($jiraUrl, $username, $password);
            $scrum15->monitorarAtividades();
            // Adicionar código para registrar eventos aqui
        } catch (Exception $e) {
            echo "Error: " . $e->getMessage() . "\n";
        }
    }
}

if (__name__ == "__main__") {
    Scrum15::main($argv);
}