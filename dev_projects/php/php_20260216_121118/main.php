<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Jira;

class JiraTracker {
    private $jira;

    public function __construct($jiraUrl, $username, $password) {
        $this->jira = new Jira($jiraUrl, $username, $password);
    }

    public function createIssue($issueData) {
        try {
            $response = $this->jira->createIssue($issueData);
            return $response;
        } catch (\Exception $e) {
            throw new Exception("Failed to create issue: " . $e->getMessage());
        }
    }

    public function updateIssue($issueId, $updateData) {
        try {
            $response = $this->jira->updateIssue($issueId, $updateData);
            return $response;
        } catch (\Exception $e) {
            throw new Exception("Failed to update issue: " . $e->getMessage());
        }
    }

    public function deleteIssue($issueId) {
        try {
            $this->jira->deleteIssue($issueId);
            return true;
        } catch (\Exception $e) {
            throw new Exception("Failed to delete issue: " . $e->getMessage());
        }
    }
}

// Função para executar o script como um programa de linha de comando
if (php_sapi_name() === 'cli') {
    // Configurações do Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Instancia o JiraTracker
    $tracker = new JiraTracker($jiraUrl, $username, $password);

    // Exemplo de criação de um novo issue
    $issueData = [
        'project' => ['key' => 'YOUR-PROJECT'],
        'summary' => 'Example Issue',
        'description' => 'This is an example issue created using PHP Agent with Jira.',
        'issuetype' => ['name' => 'Bug']
    ];

    try {
        $response = $tracker->createIssue($issueData);
        echo "Issue created successfully: " . json_encode($response, JSON_PRETTY_PRINT) . "\n";
    } catch (Exception $e) {
        echo "Error creating issue: " . $e->getMessage() . "\n";
    }
}