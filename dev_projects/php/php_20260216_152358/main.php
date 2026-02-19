<?php

// Importar classes necessárias
require_once 'JiraClient.php';
require_once 'ActivityTracker.php';

class PHPAgent {
    private $jiraClient;
    private $activityTracker;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
        $this->activityTracker = new ActivityTracker();
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            // Adicionar atividade ao issue
            $this->activityTracker.addActivity($issueKey, $activityDescription);

            // Salvar o estado atual do issue
            $this->jiraClient.updateIssueStatus($issueKey, 'In Progress');

            echo "Atividade adicionada e estado atualizado com sucesso.";
        } catch (Exception $e) {
            echo "Erro ao adicionar atividade: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do PHP Agent
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar instância do PHPAgent
        $phpAgent = new PHPAgent($jiraUrl, $username, $password);

        // Exemplo de uso
        $issueKey = 'ABC-123';
        $activityDescription = 'Realização da tarefa 1/4';

        $phpAgent->trackActivity($issueKey, $activityDescription);
    }
}

// Executar o script principal
PHPAgent::main();