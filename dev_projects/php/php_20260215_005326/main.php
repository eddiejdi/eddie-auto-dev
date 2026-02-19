<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client as JiraClient;
use Jira\Issue as Issue;

class Scrum15JiraIntegration {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        // Inicializar o cliente do Jira
        $this->jiraClient = new JiraClient([
            'url' => $jiraUrl,
            'auth' => [$username, $password]
        ]);

        // Selecionar uma tarefa específica (exemplo: ID 123)
        $this->issueId = 123;
    }

    public function monitorarAtividades() {
        try {
            // Obter a tarefa do Jira
            $issue = $this->jiraClient->getIssue($this->issueId);

            // Exibir informações da tarefa
            echo "Título: " . $issue->getTitle() . "\n";
            echo "Descrição: " . $issue->getDescription() . "\n";
            echo "Status: " . $issue->getStatus()->getName() . "\n";

            // Simular monitoramento de atividades (exemplo)
            sleep(5);

            // Atualizar o status da tarefa
            $issue->setStatus($this->jiraClient->getStatus('In Progress'));
            $this->jiraClient->updateIssue($issue);
        } catch (\Exception $e) {
            echo "Erro ao monitorar atividades: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $integration = new Scrum15JiraIntegration($jiraUrl, $username, $password);
        $integration->monitorarAtividades();
    }
}

if (__name__ == "__main__") {
    Scrum15JiraIntegration::main();
}