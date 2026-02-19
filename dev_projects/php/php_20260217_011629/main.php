<?php

// Importar classes necessárias
require 'vendor/autoload.php';

// Função principal do programa
function main() {
    // Configuração da conexão com Jira
    $jiraUrl = 'https://your-jira-instance.com';
    $jiraUsername = 'your-username';
    $jiraPassword = 'your-password';

    // Criar uma instância de PHP Agent
    $phpAgent = new \PhpAgent\Agent($jiraUrl, $jiraUsername, $jiraPassword);

    // Definir a tarefa que será registrada no Jira
    $taskTitle = 'Teste Tarefa';
    $taskDescription = 'Descrição da tarefa de teste';

    // Registrar a tarefa no Jira
    $phpAgent->createIssue($taskTitle, $taskDescription);

    echo "Tarefa registrada com sucesso!";
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}