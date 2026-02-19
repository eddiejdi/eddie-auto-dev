<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Função para iniciar a sessão com o PHP Agent
function startPhpAgent() {
    $agent = new PhpAgent();
    $agent->start();
}

// Função para enviar dados ao Jira
function sendToJira($issueKey, $summary, $description) {
    // Configurar as credenciais do Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Criar o payload do issue
    $payload = [
        'fields' => [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => $summary,
            'description' => $description,
            'issuetype' => ['name' => 'Task']
        ]
    ];

    // Criar a requisição POST para criar o issue
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $jiraUrl . '/rest/api/2/issue');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Authorization: Basic ' . base64_encode("$username:$password")
    ]);

    // Executar a requisição e obter o resultado
    $response = curl_exec($ch);
    curl_close($ch);

    // Verificar se a requisição foi bem-sucedida
    if ($response) {
        echo "Issue created successfully: " . json_decode($response, true)['key'] . "\n";
    } else {
        echo "Failed to create issue.\n";
    }
}

// Função principal para executar o script
function main() {
    // Iniciar a sessão com o PHP Agent
    startPhpAgent();

    // Simular uma atividade em PHP
    $activity = 'Processamento de dados';

    // Enviar a atividade ao Jira
    sendToJira('YOUR_ISSUE_KEY', 'Activity: ' . $activity, 'Description of the activity');

    // Finalizar a sessão com o PHP Agent
    PhpAgent::stop();
}

// Verificar se o script foi executado como um programa principal
if (__name__ == "__main__") {
    main();
}