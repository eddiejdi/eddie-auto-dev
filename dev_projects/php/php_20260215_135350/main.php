<?php

// Importar classes necessárias
require_once 'JiraClient.php';
require_once 'PHPAgent.php';

class Scrum15 {
    private $jiraClient;
    private $phpAgent;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
        $this->phpAgent = new PHPAgent();
    }

    public function registerEvent($event) {
        // Registrar o evento em PHP Agent
        $this->phpAgent->registerEvent($event);

        // Registrar o evento no Jira
        $issueId = $this->jiraClient->createIssue('Scrum 15 Event', 'This is a test event for Scrum 15');
        $this->jiraClient->addCommentToIssue($issueId, $event);
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Evento a ser registrado
        $event = 'User registered on the platform';

        // Registrar o evento
        $scrum15->registerEvent($event);
    }
}

// Executar o script
Scrum15::main();