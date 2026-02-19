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

// Verificar se o script foi executado diretamente e não via require ou include
if (__name__ == "__main__") {
    main();
}