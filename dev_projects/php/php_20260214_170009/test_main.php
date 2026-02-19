<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Config;

// Configurar a configuração do PHP Agent
$config = new Config();
$config->setServer('http://localhost:8080');
$config->setProjectKey('YOUR_PROJECT_KEY');

// Criar uma instância do PHP Agent
$agent = new Agent($config);

// Função principal
function main() {
    // Iniciar o monitoramento
    $agent->start();

    // Simular atividades em tempo real
    while (true) {
        try {
            // Simula uma operação de banco de dados
            sleep(1);
            echo "Atividade simulada: Executando consulta ao banco de dados\n";
        } catch (Exception $e) {
            // Tratar erros
            echo "Erro: " . $e->getMessage() . "\n";
        }
    }

    // Finalizar o monitoramento
    $agent->stop();
}

// Teste para verificar se a função main é chamada corretamente
function testMainIsCalled() {
    global $main;
    $main = function() {};
    call_user_func($main);
    expect($main)->toHaveBeenCalled();
}

// Teste para verificar se o PHP Agent está configurado corretamente
function testPhpAgentConfiguredCorrectly() {
    global $config;
    expect($config->getServer())->toBe('http://localhost:8080');
    expect($config->getProjectKey())->toBe('YOUR_PROJECT_KEY');
}

// Teste para verificar se a função main inicia o monitoramento corretamente
function testMainStartsMonitoring() {
    global $agent;
    $agent->start();
    expect($agent->isRunning())->toBe(true);
}

// Teste para verificar se a função main finaliza o monitoramento corretamente
function testMainStopsMonitoring() {
    global $agent;
    $agent->stop();
    expect($agent->isRunning())->toBe(false);
}