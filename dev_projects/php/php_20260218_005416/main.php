<?php

// Importar classes necessárias
use JiraClient\Client;
use JiraClient\Issue;
use JiraClient\Log;

class Scrum15 {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password) {
        // Criar cliente para Jira
        $this->jiraClient = new Client($jiraUrl);
        $this->jiraClient->login($username, $password);

        // Selecionar o issue pelo ID
        $issueId = '12345'; // Substitua pelo ID do issue em Jira
        $this->issueId = $issueId;
    }

    public function monitorarAtividades() {
        try {
            // Obter informações do issue
            $issue = $this->jiraClient->getIssue($this->issueId);

            // Logar as atividades no console
            echo "Issue {$issue['key']}:\n";
            foreach ($issue['fields']['comment'] as $comment) {
                echo "- {$comment['body']}\n";
            }
        } catch (Exception $e) {
            // Tratar erros e logar em arquivo
            Log::error("Error monitoring issue: " . $e->getMessage());
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Monitorar atividades do issue
        $scrum15->monitorarAtividades();
    }
}

// Executar o script como um programa CLI
if (__name__ == "__main__") {
    Scrum15::main();
}