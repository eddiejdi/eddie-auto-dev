<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new Client($jiraUrl);
        $this->jiraClient->login($username, $password);
    }

    public function getIssue($issueId) {
        $this->issueId = $issueId;
        return $this->jiraClient->getIssue($issueId);
    }

    public function updateStatus($status) {
        $issue = $this->getIssue($this->issueId);
        $issue->update(array('fields' => array('status' => array('name' => $status))));
    }
}

// Função main para executar o script
function main() {
    // Configurações do Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Instanciar a classe Scrum15
    $scrum15 = new Scrum15($jiraUrl, $username, $password);

    // Obter uma tarefa específica
    $issueId = 'YOUR-ISSUE-ID'; // Substitua pelo ID da tarefa que você deseja monitorar
    $issue = $scrum15->getIssue($issueId);

    echo "Título: " . $issue->fields['summary'] . "\n";
    echo "Status atual: " . $issue->fields['status']['name'] . "\n";

    // Atualizar o status da tarefa
    $newStatus = 'In Progress';
    $scrum15->updateStatus($newStatus);
}

// Verificar se o script é executado como um programa de linha de comando
if (php_sapi_name() === 'cli') {
    main();
}