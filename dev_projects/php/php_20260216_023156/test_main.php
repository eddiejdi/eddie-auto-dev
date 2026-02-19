<?php

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;
use PhpAgent\Jira\Comment;

// Teste para criar um novo issue no Jira
function testCreateIssue() {
    // Configurar o PHP Agent
    $agent = new PhpAgent\Agent();

    // Conexão com Jira
    $client = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    // Dados de teste para criar um novo issue
    $issueData = [
        'project' => 'YOUR_PROJECT_KEY',
        'summary' => 'Teste Issue',
        'description' => 'Descrição do teste issue'
    ];

    // Chamada à função createIssue
    $issue = createIssue($client, $issueData);

    // Verificação se o issue foi criado corretamente
    assert($issue instanceof Issue);
    assert($issue->project === 'YOUR_PROJECT_KEY');
    assert($issue->summary === 'Teste Issue');
    assert($issue->description === 'Descrição do teste issue');
}

// Teste para comentar em um issue no Jira
function testCommentIssue() {
    // Configurar o PHP Agent
    $agent = new PhpAgent\Agent();

    // Conexão com Jira
    $client = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    // Dados de teste para comentar em um issue
    $issueKey = 'TEST-123';
    $commentData = [
        'body' => "Comentário do teste"
    ];

    // Chamada à função commentIssue
    $comment = commentIssue($client, $issueKey, $commentData);

    // Verificação se o comentário foi adicionado corretamente
    assert($comment instanceof Comment);
    assert($comment->issue === 'TEST-123');
    assert($comment->body === "Comentário do teste");
}

// Teste para monitorar atividades no sistema Jira
function testMonitorActivity() {
    // Configurar o PHP Agent
    $agent = new PhpAgent\Agent();

    // Conexão com Jira
    $client = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    // Dados de teste para monitorar atividades
    $query = "SELECT * FROM your-jira-table";

    try {
        $result = $client->executeQuery($query);
        
        foreach ($result as $row) {
            // Criar um novo issue no Jira
            $issueData = [
                'project' => 'YOUR_PROJECT_KEY',
                'summary' => $row['activity_summary'],
                'description' => $row['activity_description']
            ];
            $issue = createIssue($client, $issueData);
            
            // Comentar em um issue no Jira
            $commentData = [
                'body' => "Activity: {$row['activity_summary']}"
            ];
            commentIssue($client, $issue->key, $commentData);
        }
    } catch (\Exception $e) {
        echo "Error monitoring activity: " . $e->getMessage();
    }
}