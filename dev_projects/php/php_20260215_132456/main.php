<?php

// Importar classes necessárias
use PhpAgent\Agent;
use PhpAgent\Log;

class JiraLogger {
    private $agent;
    private $log;

    public function __construct($url, $token) {
        // Configurar o PHP Agent para enviar logs para Jira
        $this->agent = new Agent([
            'url' => $url,
            'token' => $token,
            'projectKey' => 'YOUR_PROJECT_KEY',
            'issueType' => 'BUG'
        ]);

        // Inicializar o log
        $this->log = new Log();
    }

    public function logMessage($message) {
        // Adicionar mensagem ao log
        $this->log->addLogEntry($message);

        // Enviar log para Jira
        try {
            $response = $this->agent->sendLogs();
            echo "Log enviado com sucesso: " . json_encode($response);
        } catch (Exception $e) {
            echo "Erro ao enviar log: " . $e->getMessage();
        }
    }

    public function main() {
        // Exemplo de uso
        $this->logMessage("Este é um exemplo de log enviado pelo PHP Agent para Jira.");
    }
}

// Configuração do PHP Agent
$url = 'https://your-jira-instance.atlassian.net/rest/api/3/log';
$token = 'YOUR_JIRA_TOKEN';

// Criar instância do logger e executar o main()
$jiraLogger = new JiraLogger($url, $token);
$jiraLogger->main();