<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Config;

// Configurar o PHP Agent
$config = new Config();
$config->setServer('http://localhost:8080');
$config->setToken('your_token_here');

$agent = new Agent($config);

// Função para iniciar a integração com Jira
function startJiraIntegration() {
    // Implementar a lógica para integrar com Jira usando o PHP Agent
    $agent->sendRequest('/rest/api/2/issue', [
        'fields' => [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'Teste de integração',
            'description' => 'Descrição do teste',
            'issuetype' => ['name' => 'Bug']
        ]
    ]);

    // Verificar o status da requisição
    $response = $agent->getResponse();
    if ($response['status'] === 201) {
        echo "Integração com Jira bem-sucedida!\n";
    } else {
        echo "Falha na integração com Jira.\n";
    }
}

// Função principal
function main() {
    // Iniciar a integração com Jira
    startJiraIntegration();
}

// Executar o programa
if (__name__ == "__main__") {
    main();
}