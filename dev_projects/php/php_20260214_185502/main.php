<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

// Função principal do programa
function main() {
    // Configuração do Jira
    $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    // Criar um novo issue
    $issue = new Issue();
    $issue->setSummary('Teste de Scrum');
    $issue->setDescription('Este é um teste para a integração com Jira usando PHP Agent.');
    $issue->setType('bug');

    // Adicionar tags ao issue
    $issue->addTag('scrum');
    $issue->addTag('test');

    // Criar o issue no Jira
    $createdIssue = $jira->createIssue($issue);

    echo "Issue criado com ID: {$createdIssue->getId()}\n";

    // Monitoramento de atividades (exemplo)
    $activity = $jira->getActivity('your-username', 'your-password');
    echo "Atividade monitorada:\n";
    print_r($activity);
}

// Executar o programa
main();