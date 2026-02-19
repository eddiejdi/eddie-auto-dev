<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do PHP Agent
$agent = new \PhpAgent\Agent('your-jira-project-key', 'your-php-agent-token');

// Função para iniciar o processo de integração com Jira
function startIntegration() {
    try {
        // Realizar a autenticação no PHP Agent
        $agent->authenticate();

        // Definir as atividades a serem trackadas
        $activities = [
            ['title' => 'Início do projeto', 'status' => 'Open'],
            ['title' => 'Adição de usuário', 'status' => 'Open'],
            ['title' => 'Configuração do banco de dados', 'status' => 'Open'],
            ['title' => 'Teste da integração', 'status' => 'In Progress']
        ];

        // Loop para trackar as atividades
        foreach ($activities as $activity) {
            // Criar uma nova atividade no PHP Agent
            $agent->createActivity($activity['title'], $activity['status']);

            // Simular o processamento da atividade (por exemplo, um sleep)
            sleep(2);

            // Atualizar o status da atividade
            $agent->updateActivityStatus($activity['title'], 'In Progress');
        }

        // Finalizar a integração no PHP Agent
        $agent->finish();

        echo "Integração com Jira concluída com sucesso.\n";
    } catch (\Exception $e) {
        echo "Erro ao integrar com Jira: " . $e->getMessage() . "\n";
    }
}

// Função principal do script
function main() {
    startIntegration();
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}