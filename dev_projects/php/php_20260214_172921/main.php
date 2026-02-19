<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class Scrum15 {
    private $jiraClient;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
    }

    public function createIssue($issueData) {
        try {
            $issue = new Issue();
            foreach ($issueData as $key => $value) {
                $issue->$key = $value;
            }
            return $this->jiraClient->createIssue($issue);
        } catch (\Exception $e) {
            echo "Error creating issue: " . $e->getMessage() . "\n";
            return null;
        }
    }

    public function updateIssue($issueId, $updateData) {
        try {
            $issue = new Issue();
            foreach ($updateData as $key => $value) {
                $issue->$key = $value;
            }
            return $this->jiraClient->updateIssue($issueId, $issue);
        } catch (\Exception $e) {
            echo "Error updating issue: " . $e->getMessage() . "\n";
            return null;
        }
    }

    public function deleteIssue($issueId) {
        try {
            return $this->jiraClient->deleteIssue($issueId);
        } catch (\Exception $e) {
            echo "Error deleting issue: " . $e->getMessage() . "\n";
            return null;
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar instância da classe Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Exemplo de criação de issue
        $issueData = [
            'summary' => 'New feature request',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => 'JohnDoe'
        ];
        $createdIssue = $scrum15->createIssue($issueData);
        if ($createdIssue) {
            echo "Issue created successfully: " . $createdIssue->key . "\n";
        }

        // Exemplo de atualização de issue
        $updateData = [
            'description' => 'Update the feature request with new details',
            'priority' => 'Medium'
        ];
        $updatedIssue = $scrum15->updateIssue($createdIssue->id, $updateData);
        if ($updatedIssue) {
            echo "Issue updated successfully: " . $updatedIssue->key . "\n";
        }

        // Exemplo de deleção de issue
        $deletedIssue = $scrum15->deleteIssue($createdIssue->id);
        if ($deletedIssue) {
            echo "Issue deleted successfully.\n";
        }
    }
}

// Executar o script principal
Scrum15::main();