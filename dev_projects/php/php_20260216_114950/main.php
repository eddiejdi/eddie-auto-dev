<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

// Função principal do programa
function main() {
    // Configuração do Jira Client
    $jiraClient = new JiraClient('https://your-jira-instance.com', 'your-username', 'your-password');

    // Criar um novo issue
    $issueData = [
        'project' => ['key' => 'YOUR_PROJECT_KEY'],
        'summary' => 'Teste de Issue',
        'description' => 'Descrição do Issue',
        'priority' => ['name' => 'Normal'],
        'status' => ['name' => 'To Do']
    ];

    $issue = new Issue($issueData);
    $createdIssue = $jiraClient->createIssue($issue);

    // Exibir informações sobre o issue criado
    echo "Issue Criado: " . $createdIssue->getKey() . "\n";
}

// Verificar se o script foi executado como o programa principal
if (__name__ == "__main__") {
    main();
}