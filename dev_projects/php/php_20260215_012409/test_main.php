<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do PHP Agent para Jira
$agent = new PhpAgent\Jira\JiraAgent();
$agent->setProjectKey('YOUR_PROJECT_KEY');
$agent->setIssueType('TASK');
$agent->setSummary('Teste de Integração com Jira');

// Função para adicionar atividades ao Jira
function addActivityToJira($activity) {
    $agent->addActivity($activity);
}

// Função principal do programa
function main() {
    // Exemplo de atividade
    $activity = [
        'summary' => 'Teste de Integração com PHP Agent',
        'description' => 'Este é um teste para integrar o PHP Agent com Jira',
        'assignee' => 'USER_ID'
    ];

    // Adicionar a atividade ao Jira
    addActivityToJira($activity);

    echo "Atividade adicionada com sucesso!";
}

// Executar o programa
if (__name__ == "__main__") {
    main();
}