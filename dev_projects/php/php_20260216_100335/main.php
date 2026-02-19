<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraTracker {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function createIssue($projectKey, $summary, $description) {
        $issueData = [
            'fields' => [
                'project' => ['key' => $projectKey],
                'summary' => $summary,
                'description' => $description
            ]
        ];

        return $this->jiraClient->createIssue($issueData);
    }

    public function updateIssue($issueId, $updateData) {
        return $this->jiraClient->updateIssue($issueId, $updateData);
    }
}

// Função principal para executar o script
function main() {
    // Configurações do Jira
    $url = 'http://your-jira-instance.com';
    $username = 'your-username';
    $password = 'your-password';

    // Instanciar a classe JiraTracker
    $jiraTracker = new JiraTracker($url, $username, $password);

    // Criar uma nova tarefa no Jira
    $projectKey = 'YOUR_PROJECT_KEY';
    $summary = 'Teste de Integração PHP Agent com Jira';
    $description = 'Este é um teste para integrar o PHP Agent com o Jira.';
    $issue = $jiraTracker->createIssue($projectKey, $summary, $description);

    // Exibir a ID da tarefa criada
    echo "Tarefa criada com ID: " . $issue['id'] . "\n";

    // Atualizar uma tarefa existente no Jira
    $updateData = [
        'fields' => [
            'status' => ['name' => 'In Progress']
        ]
    ];
    $updatedIssue = $jiraTracker->updateIssue($issue['id'], $updateData);

    // Exibir as informações atualizadas da tarefa
    echo "Tarefa atualizada com ID: " . $updatedIssue['id'] . "\n";
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}