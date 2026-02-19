<?php

// Configuração do Composer para instalar as dependências
require 'vendor/autoload.php';

use App\JiraClient;
use App\ActivityLogger;

// Função main para executar a aplicação
function main() {
    // Instancia o cliente Jira
    $jiraClient = new JiraClient();

    // Instancia o logger de atividades
    $activityLogger = new ActivityLogger();

    // Simulação de uma atividade em PHP
    $activityLog = "PHP Agent integrado com Jira";

    try {
        // Registra a atividade no Jira
        $jiraClient->logActivity($activityLog);

        // Registra a atividade no logger local
        $activityLogger->logActivity($activityLog);
    } catch (Exception $e) {
        echo "Erro: " . $e->getMessage();
    }
}

// Executa a função main
main();