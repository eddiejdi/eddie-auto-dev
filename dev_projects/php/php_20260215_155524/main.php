<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issueTracker;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl);
        $this->issueTracker = new Issue($this->jiraClient);
    }

    public function registerEvent($eventName, $eventData) {
        // Registrar o evento no Jira
        $issue = new Issue();
        $issue->setKey('SCRUM15-1');
        $issue->setDescription("Event: {$eventName} - Data: " . date('Y-m-d H:i:s'));
        $issue->addComment($eventData);
        $this->issueTracker.createIssue($issue);

        echo "Evento registrado com sucesso!\n";
    }

    public function monitorActivity() {
        // Monitorar atividades do usuário
        $user = 'username';
        $issues = $this->issueTracker.searchIssues(['assignee' => $user]);

        foreach ($issues as $issue) {
            echo "Issue: {$issue->getKey()} - Status: {$issue->getStatus()->getName()}\n";
        }
    }

    public static function main() {
        // Configurar a conexão com o Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância do Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Registrar um evento
        $eventName = 'User Login';
        $eventData = "Usuário {$username} logou no sistema.";
        $scrum15->registerEvent($eventName, $eventData);

        // Monitorar atividades do usuário
        $scrum15->monitorActivity();
    }
}

// Executar o código principal
Scrum15::main();