<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

// Configuração do cliente Jira
$client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-api-token');

// Função para criar uma nova tarefa no Jira
function createTask($client, $projectKey, $summary, $description) {
    $issueData = [
        'fields' => [
            'project' => ['key' => $projectKey],
            'summary' => $summary,
            'description' => $description,
            'issuetype' => ['name' => 'Task'],
        ],
    ];

    try {
        $issue = new Issue($client, $issueData);
        echo "Tarefa criada com sucesso: {$issue->getKey()}\n";
    } catch (Exception $e) {
        echo "Erro ao criar tarefa: " . $e->getMessage() . "\n";
    }
}

// Função para monitorar atividades
function monitorActivities($client, $projectKey) {
    try {
        $issues = $client->search('project=' . $projectKey);
        
        foreach ($issues as $issue) {
            echo "Tarefa {$issue->getKey()}: {$issue->getSummary()} - Status: {$issue->getStatus()->getName()}\n";
        }
    } catch (Exception $e) {
        echo "Erro ao monitorar atividades: " . $e->getMessage() . "\n";
    }
}

// Função principal
function main() {
    // Configuração do projeto
    $projectKey = 'YOUR_PROJECT_KEY';

    // Criar uma nova tarefa
    createTask($client, $projectKey, 'Nova Tarefa', 'Descrição da nova tarefa');

    // Monitorar atividades
    monitorActivities($client, $projectKey);
}

// Executar o programa
if (__name__ == "__main__") {
    main();
}