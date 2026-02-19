<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do PHP Agent
$agent = new PhpAgent\Agent();
$agent->setToken('YOUR_JIRA_TOKEN');
$agent->setProjectKey('YOUR_PROJECT_KEY');

// Função para criar um ticket em Jira
function createJiraTicket($title, $description) {
    global $agent;

    // Criar o ticket
    $issue = [
        'fields' => [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => $title,
            'description' => $description,
            'issuetype' => ['name' => 'Bug']
        ]
    ];

    // Enviar o ticket para Jira
    $response = $agent->createIssue($issue);

    // Verificar se o ticket foi criado com sucesso
    if ($response['id']) {
        echo "Ticket criado com sucesso: {$response['id']}\n";
    } else {
        echo "Erro ao criar ticket: " . json_encode($response) . "\n";
    }
}

// Função principal
function main() {
    // Exemplo de uso da função createJiraTicket
    $title = "Teste do PHP Agent com Jira";
    $description = "Este é um teste para verificar a integração do PHP Agent com Jira.";
    createJiraTicket($title, $description);
}

// Verificar se o script foi executado como o programa principal
if (__name__ == "__main__") {
    main();
}