<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client as JiraClient;
use Jira\Issue as Issue;

class PhpAgent {
    private $jiraClient;
    private $issueId;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient([
            'baseUrl' => $url,
            'authType' => 'basic',
            'username' => $username,
            'password' => $password
        ]);
    }

    public function createIssue($summary, $description) {
        $issueData = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Task']
            ]
        ];

        try {
            $this->issueId = $this->jiraClient->issues()->create($issueData);
            return "Issue created with ID: {$this->issueId}";
        } catch (\Exception $e) {
            return "Error creating issue: {$e->getMessage()}";
        }
    }

    public function updateIssueStatus($status) {
        try {
            $issue = new Issue([
                'id' => $this->issueId,
                'fields' => [
                    'status' => ['name' => $status]
                ]
            ]);

            $this->jiraClient->issues()->update($issue);
            return "Issue status updated to: {$status}";
        } catch (\Exception $e) {
            return "Error updating issue status: {$e->getMessage()}";
        }
    }

    public function main() {
        // Configuração do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma nova tarefa
        $summary = 'Teste de PHP Agent com Jira';
        $description = 'Este é um teste para integrar o PHP Agent com Jira.';
        echo $this->createIssue($summary, $description);

        // Atualizar a status da tarefa para "In Progress"
        $status = 'In Progress';
        echo $this->updateIssueStatus($status);
    }
}

// Executar o programa
if (__name__ == "__main__") {
    PhpAgent::main();
}