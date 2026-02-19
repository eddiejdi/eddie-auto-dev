<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do PHP Agent
$agent = new PhpAgent\Agent([
    'host' => 'localhost',
    'port' => 8080,
]);

// Função para enviar um log para Jira
function sendLogToJira($log) {
    global $agent;

    // Criar o corpo do log
    $body = [
        'issue' => [
            'fields' => [
                'summary' => 'Novo Log',
                'description' => $log,
            ],
        ],
    ];

    // Enviar o log para Jira
    try {
        $response = $agent->post('rest/api/2/issue', json_encode($body));
        echo "Log enviado com sucesso: " . $response;
    } catch (\Exception $e) {
        echo "Erro ao enviar log para Jira: " . $e->getMessage();
    }
}

// Função principal do script
function main() {
    // Log de exemplo
    $log = "Novo log enviado via PHP Agent";

    // Enviar o log para Jira
    sendLogToJira($log);
}

// Executar o script se for CLI
if (php_sapi_name() === 'cli') {
    main();
}