<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Report;

// Função para conectar ao Jira API
function connectToJira($url, $username, $password) {
    // Criar um objeto do cliente do Jira
    $client = new \PhpAgent\Client($url);

    // Autenticar o usuário no Jira
    if (!$client->login($username, $password)) {
        throw new Exception('Falha ao autenticar no Jira');
    }

    return $client;
}

// Função para criar um novo ticket no Jira
function createTicket($client, $summary, $description) {
    // Criar um novo ticket
    $ticket = $client->createIssue([
        'fields' => [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => $summary,
            'description' => $description,
            'issuetype' => ['name' => 'Bug']
        ]
    ]);

    return $ticket;
}

// Função para enviar um relatório via email
function sendReportViaEmail($client, $report) {
    // Enviar o relatório via e-mail
    $client->sendEmail([
        'to' => 'your-email@example.com',
        'subject' => 'Relatório de Atividades',
        'body' => $report,
        'attachments' => [
            ['path' => 'path/to/your/report.pdf', 'name' => 'report.pdf']
        ]
    ]);
}

// Função principal
function main() {
    // Configurações do PHP Agent
    $agent = new Agent([
        'url' => 'http://localhost:8080',
        'username' => 'your-php-agent-username',
        'password' => 'your-php-agent-password'
    ]);

    try {
        // Conectar ao Jira API
        $client = connectToJira('https://your-jira-instance.atlassian.net', 'your-jira-username', 'your-jira-password');

        // Criar um novo ticket no Jira
        $summary = 'Novo Ticket - PHP Agent';
        $description = 'Este é um exemplo de relatório via email enviado pelo PHP Agent.';
        $ticket = createTicket($client, $summary, $description);

        // Gerar o relatório
        $report = "Relatório do Ticket {$ticket['key']}\n";
        $report .= "Summary: {$ticket['fields']['summary']}\n";
        $report .= "Description: {$ticket['fields']['description']}\n";

        // Enviar o relatório via email
        sendReportViaEmail($client, $report);

        echo "Relatório enviado com sucesso para {$ticket['key']}.\n";
    } catch (Exception $e) {
        echo "Erro: " . $e->getMessage() . "\n";
    }
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}