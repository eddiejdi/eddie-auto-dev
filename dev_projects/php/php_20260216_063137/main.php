<?php

// Importar classes necessárias
use PhpAgent\JiraClient;
use PhpAgent\JiraIssue;

// Configuração do PHP Agent para Jira
$agent = new JiraClient('https://your-jira-instance.atlassian.net', 'username', 'password');

try {
    // Função para criar um novo issue no Jira
    function createJiraIssue($projectKey, $summary, $description, $assignee) {
        $issue = new JiraIssue();
        $issue->setProjectKey($projectKey);
        $issue->setTitle($summary);
        $issue->setDescription($description);
        $issue->setAssignee($assignee);

        return $agent->createIssue($issue);
    }

    // Função para atualizar um issue no Jira
    function updateJiraIssue($issueId, $summary, $description) {
        $issue = new JiraIssue();
        $issue->setId($issueId);
        $issue->setTitle($summary);
        $issue->setDescription($description);

        return $agent->updateIssue($issue);
    }

    // Função para buscar um issue no Jira
    function getJiraIssue($issueId) {
        return $agent->getIssue($issueId);
    }

    // Exemplo de uso das funções
    $projectKey = 'YOUR_PROJECT_KEY';
    $summary = 'New task for the project';
    $description = 'This is a new task created by PHP Agent for Jira.';
    $assignee = 'user123';

    $newIssue = createJiraIssue($projectKey, $summary, $description, $assignee);
    echo "Created issue: " . $newIssue->getTitle() . "\n";

    $issueId = $newIssue->getId();
    $updatedIssue = updateJiraIssue($issueId, 'Updated task for the project', $description);
    echo "Updated issue: " . $updatedIssue->getTitle() . "\n";

    $issue = getJiraIssue($issueId);
    echo "Fetched issue: " . $issue->getTitle() . "\n";
} catch (Exception $e) {
    echo "Error: " . $e->getMessage();
}