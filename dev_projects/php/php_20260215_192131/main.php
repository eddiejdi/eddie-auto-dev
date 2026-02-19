<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira;
use PhpAgent\Exception;

// Função main para executar a integração com Jira
function main() {
    // Configuração do PHP Agent
    $agent = new Jira([
        'url' => 'https://your-jira-instance.com',
        'username' => 'your-username',
        'password' => 'your-password'
    ]);

    try {
        // Autenticar o usuário no Jira
        $agent->login();

        // Criar uma nova tarefa no Jira
        $task = new \PhpAgent\Task([
            'project' => 'YOUR_PROJECT_KEY',
            'summary' => 'Teste de Integração com PHP Agent',
            'description' => 'Este é um teste para verificar a integração do PHP Agent com Jira.'
        ]);

        // Adicionar uma tarefa ao projeto
        $task->create();

        echo "Tarefa criada com sucesso!\n";

    } catch (Exception $e) {
        echo "Erro: " . $e->getMessage() . "\n";
    }
}

// Executar a função main
main();