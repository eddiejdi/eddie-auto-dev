<?php

// Importar as classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

// Configuração do PHP Agent para Jira
$agent = new PhpAgent\Jira\Agent(
    'https://your-jira-instance.atlassian.net/rest/api/3',
    'your-api-token'
);

try {
    // Criar uma nova issue
    $issue = new Issue();
    $issue->setProjectKey('YOUR_PROJECT_KEY');
    $issue->setSummary('Teste do PHP Agent com Jira');
    $issue->setDescription('Este é um teste para verificar a integração do PHP Agent com Jira');

    // Adicionar tags à issue
    $issue->addTag('test-php-agent');
    $issue->addTag('jira-integration');

    // Criar a issue no Jira
    $createdIssue = $agent->createIssue($issue);

    echo "Issue criada: " . $createdIssue->getKey() . "\n";

} catch (\Exception $e) {
    echo "Erro ao criar a issue: " . $e->getMessage() . "\n";
}