<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';
use Jira\JiraClient;
use Jira\Api\ClientException;

class JiraIntegration {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function createIssue($projectKey, $summary, $description) {
        try {
            $issue = [
                'fields' => [
                    'project' => ['key' => $projectKey],
                    'summary' => $summary,
                    'description' => $description
                ]
            ];

            $response = $this->jiraClient->issues()->create($issue);
            return $response;
        } catch (ClientException $e) {
            echo "Error creating issue: " . $e->getMessage();
            return null;
        }
    }

    public function updateIssue($issueKey, $summary, $description) {
        try {
            $issue = [
                'fields' => [
                    'summary' => $summary,
                    'description' => $description
                ]
            ];

            $response = $this->jiraClient->issues()->update($issueKey, $issue);
            return $response;
        } catch (ClientException $e) {
            echo "Error updating issue: " . $e->getMessage();
            return null;
        }
    }

    public function getIssue($issueKey) {
        try {
            $response = $this->jiraClient->issues()->get($issueKey);
            return $response;
        } catch (ClientException $e) {
            echo "Error getting issue: " . $e->getMessage();
            return null;
        }
    }

    public function closeIssue($issueKey) {
        try {
            $update = [
                'fields' => [
                    'status' => ['id' => 10239] // ID do status fechado em Jira
                ]
            ];

            $response = $this->jiraClient->issues()->update($issueKey, $update);
            return $response;
        } catch (ClientException $e) {
            echo "Error closing issue: " . $e->getMessage();
            return null;
        }
    }

    public function deleteIssue($issueKey) {
        try {
            $this->jiraClient->issues()->delete($issueKey);
            return true;
        } catch (ClientException $e) {
            echo "Error deleting issue: " . $e->getMessage();
            return false;
        }
    }
}

// Função main para executar o script
if (__name__ == "__main__") {
    // Configurações do Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $jiraUsername = 'your-username';
    $jiraPassword = 'your-password';

    // Instanciar a classe JiraIntegration
    $jira = new JiraIntegration($jiraUrl, $jiraUsername, $jiraPassword);

    // Criar um novo issue
    $issueKey = 'NEW-123';
    $summary = 'Teste de criação de issue';
    $description = 'Descrição do teste.';
    $createdIssue = $jira->createIssue($issueKey, $summary, $description);
    if ($createdIssue) {
        echo "Issue criado com sucesso: " . $createdIssue['key'] . "\n";
    }

    // Atualizar um issue
    $updatedSummary = 'Teste de atualização de issue';
    $updatedDescription = 'Descrição atualizada do teste.';
    $jira->updateIssue($issueKey, $updatedSummary, $updatedDescription);
    echo "Issue atualizado com sucesso.\n";

    // Obter um issue
    $issue = $jira->getIssue($issueKey);
    if ($issue) {
        print_r($issue);
    }

    // Fechar um issue
    $jira->closeIssue($issueKey);
    echo "Issue fechado com sucesso.\n";

    // Deletar um issue
    $jira->deleteIssue($issueKey);
    echo "Issue deletado com sucesso.\n";
}