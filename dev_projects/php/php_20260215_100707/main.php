<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Request;

class JiraTracker {
    private $agent;
    private $request;

    public function __construct($url, $username, $password) {
        // Inicializar o PHP Agent
        $this->agent = new Agent($url);
        $this->agent->setCredentials($username, $password);

        // Criar uma nova requisição
        $this->request = new Request();
    }

    public function trackActivity($issueKey, $activityType, $description) {
        try {
            // Adicionar atividade ao issue
            $response = $this->agent->post('/rest/api/2/issue/' . $issueKey . '/comment', [
                'fields' => [
                    'body' => [
                        'content' => [
                            ['text' => $description]
                        ]
                    ],
                    'type' => [
                        'name' => $activityType
                    ]
                ]
            ]);

            // Verificar se a requisição foi bem-sucedida
            if ($response->getStatusCode() === 201) {
                echo "Atividade adicionada com sucesso!";
            } else {
                echo "Erro ao adicionar atividade: " . $response->getBody();
            }
        } catch (Exception $e) {
            echo "Erro: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do Jira Tracker
        $jiraTracker = new JiraTracker('https://your-jira-instance.atlassian.net', 'username', 'password');

        // Exemplo de uso
        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $description = 'The task was completed successfully';

        $jiraTracker->trackActivity($issueKey, $activityType, $description);
    }
}

// Executar o script se for CLI
if (php_sapi_name() === 'cli') {
    JiraTracker::main();
}