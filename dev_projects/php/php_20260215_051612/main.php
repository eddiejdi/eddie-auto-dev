<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do PHP Agent
ini_set('xdebug.remote_enable', 1);
ini_set('xdebug.remote_host', 'localhost');
ini_set('xdebug.remote_port', '9000');

// Função para enviar logs para Jira
function sendLogToJira($log) {
    // Configurações do Jira API
    $url = 'http://your-jira-url/rest/api/2/log';
    $headers = [
        'Content-Type: application/json',
        'Authorization: Basic your-api-key'
    ];

    // JSON da log
    $jsonLog = json_encode([
        'log' => $log,
        'level' => 'info'
    ]);

    // Faz a requisição POST para Jira
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonLog);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    // Executa a requisição
    $response = curl_exec($ch);
    curl_close($ch);

    return $response;
}

// Função para capturar informações relevantes do PHP Agent
function capturePhpAgentData() {
    // Captura os dados do PHP Agent
    $data = json_decode(file_get_contents('php://input'), true);

    // Verifica se o dado é um log válido
    if (isset($data['log']) && isset($data['level'])) {
        // Envia o log para Jira
        sendLogToJira($data['log']);
    } else {
        echo "Erro: Dado inválido";
    }
}

// Função principal do sistema de tracking de atividades
function main() {
    // Captura os dados do PHP Agent
    capturePhpAgentData();
}

// Verifica se o script é executado como um arquivo standalone
if (php_sapi_name() === 'cli') {
    main();
}