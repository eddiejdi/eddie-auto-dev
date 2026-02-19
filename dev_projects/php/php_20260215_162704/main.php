<?php

// Importar as classes necessárias do PHP Agent
require_once 'PHPAgent.php';

class JiraTracker {
    private $agent;

    public function __construct($url, $username, $password) {
        // Inicializar o PHP Agent com as credenciais de autenticação
        $this->agent = new PHPAgent($url, $username, $password);
    }

    public function trackActivity($issueKey, $activityType, $details) {
        try {
            // Criar um novo registro de atividade no Jira
            $response = $this->agent->createIssueActivity(
                [
                    'issue' => ['key' => $issueKey],
                    'fields' => [
                        'comment' => [
                            'body' => $details,
                            'type' => 'text'
                        ],
                        'update' => [
                            'status' => [
                                'to' => $activityType
                            ]
                        ]
                    ]
                ]
            );

            // Verificar se a atividade foi criada com sucesso
            if ($response['status'] === 201) {
                echo "Atividade criada com sucesso.";
            } else {
                echo "Falha ao criar atividade: " . $response['error'];
            }
        } catch (Exception $e) {
            // Tratar erros de conexão ou criação de atividade
            echo "Erro: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configurações do PHP Agent
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar a classe JiraTracker
        $tracker = new JiraTracker($url, $username, $password);

        // Exemplo de uso: Criar uma atividade no issue com chave 'ABC-123'
        $issueKey = 'ABC-123';
        $activityType = 'commented'; // ou 'resolved', 'updated', etc.
        $details = "O usuário realizou um update no item.";

        $tracker->trackActivity($issueKey, $activityType, $details);
    }
}

// Executar o script principal
JiraTracker::main();