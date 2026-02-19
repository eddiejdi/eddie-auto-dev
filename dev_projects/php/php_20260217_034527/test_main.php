<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;
use Jira\Comment;

// Configuração do cliente Jira
$client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

// Função para criar um novo issue no Jira
function createJiraIssue($projectKey, $summary, $description) {
    try {
        $issue = new Issue();
        $issue->setProjectId($client->getProjectById($projectKey)->getId());
        $issue->setSummary($summary);
        $issue->setDescription($description);

        $response = $client->createIssue($issue);
        return $response;
    } catch (\Exception $e) {
        echo "Error creating issue: " . $e->getMessage();
        return null;
    }
}

// Função para adicionar um comentário a um issue no Jira
function addJiraComment($issueId, $commentText) {
    try {
        $comment = new Comment();
        $comment->setText($commentText);

        $response = $client->addComment($issueId, $comment);
        return $response;
    } catch (\Exception $e) {
        echo "Error adding comment: " . $e->getMessage();
        return null;
    }
}

// Função principal
function main() {
    // Configuração do projeto e issue
    $projectKey = 'YOUR_PROJECT_KEY';
    $summary = 'Test Issue';
    $description = 'This is a test issue created using PHP Agent with Jira.';
    $issueId = null;

    // Criar o novo issue no Jira
    $issue = createJiraIssue($projectKey, $summary, $description);
    if ($issue) {
        echo "Issue created successfully: " . $issue->getKey() . "\n";

        // Adicionar um comentário ao issue
        $commentText = 'This is a test comment added using PHP Agent with Jira.';
        addJiraComment($issue->getKey(), $commentText);
    }
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}