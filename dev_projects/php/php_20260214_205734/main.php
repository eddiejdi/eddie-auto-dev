<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Entity\Issue;

class JiraScrum15 {
    private $client;

    public function __construct($jiraUrl, $username, $password) {
        $this->client = new Client($jiraUrl, $username, $password);
    }

    public function createIssue($summary, $description, $priority, $assignee) {
        try {
            $issue = new Issue();
            $issue->setSummary($summary);
            $issue->setDescription($description);
            $issue->setPriority($priority);
            $issue->setAssignee($assignee);

            $this->client->createIssue($issue);
            echo "Issue created successfully.\n";
        } catch (\Exception $e) {
            echo "Error creating issue: " . $e->getMessage() . "\n";
        }
    }

    public function updateIssue($issueId, $summary, $description, $priority, $assignee) {
        try {
            $issue = new Issue();
            $issue->setSummary($summary);
            $issue->setDescription($description);
            $issue->setPriority($priority);
            $issue->setAssignee($assignee);

            $this->client->updateIssue($issueId, $issue);
            echo "Issue updated successfully.\n";
        } catch (\Exception $e) {
            echo "Error updating issue: " . $e->getMessage() . "\n";
        }
    }

    public function deleteIssue($issueId) {
        try {
            $this->client->deleteIssue($issueId);
            echo "Issue deleted successfully.\n";
        } catch (\Exception $e) {
            echo "Error deleting issue: " . $e->getMessage() . "\n";
        }
    }

    public function getIssues() {
        try {
            $issues = $this->client->getIssues();
            foreach ($issues as $issue) {
                echo "Issue ID: " . $issue->getId() . ", Summary: " . $issue->getSummary() . "\n";
            }
        } catch (\Exception $e) {
            echo "Error retrieving issues: " . $e->getMessage() . "\n";
        }
    }

    public function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar o cliente para Jira
        $client = new Client($jiraUrl, $username, $password);

        // Exemplo de criação de uma tarefa
        $summary = 'Implement PHP Agent for Jira';
        $description = 'Track tasks in Jira using PHP Agent.';
        $priority = 'High';
        $assignee = 'user123';

        $client->createIssue($summary, $description, $priority, $assignee);

        // Exemplo de atualização de uma tarefa
        $issueId = 12345; // ID da tarefa existente
        $newSummary = 'Update PHP Agent for Jira';
        $newDescription = 'Fix bugs in PHP Agent.';
        $newPriority = 'Medium';
        $newAssignee = 'user456';

        $client->updateIssue($issueId, $newSummary, $newDescription, $newPriority, $newAssignee);

        // Exemplo de deleção de uma tarefa
        $issueToDeleteId = 12345; // ID da tarefa existente

        $client->deleteIssue($issueToDeleteId);

        // Exemplo de listagem de todas as tarefas
        $client->getIssues();
    }
}

// Executar o programa principal
if (__name__ == "__main__") {
    $jiraScrum15 = new JiraScrum15();
    $jiraScrum15->main();
}