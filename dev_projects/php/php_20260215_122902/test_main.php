<?php

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Model\Issue;

class Scrum15Test extends \PHPUnit\Framework\TestCase {
    protected $jiraClient;

    public function setUp(): void {
        // Configuração do Jira Client
        $this->jiraClient = new Client('https://your-jira-url.com', 'username', 'password');
    }

    public function testTrackActivitySuccess() {
        // Cria um issue válido
        $issueKey = 'SCM-001';
        $issue = new Issue();
        $issue->setSummary('Teste de Atividade');
        $issue->setDescription('Descrição do teste de atividade');

        // Salva o issue no Jira
        $this->jiraClient->createIssue($issue);

        // Chama a função trackActivity com um status válido
        $scrum15 = new Scrum15('https://your-jira-url.com', 'username', 'password');
        $status = 'In Progress';
        $scrum15->trackActivity($issueKey, $status);

        // Verifica se o status foi atualizado corretamente
        $updatedIssue = $this->jiraClient->getIssue($issueKey);
        $this->assertEquals($status, $updatedIssue->getStatus()->getName());

        // Remove o issue do Jira (opcional)
        $this->jiraClient->deleteIssue($issueKey);
    }

    public function testTrackActivityFailure() {
        // Cria um issue válido
        $issueKey = 'SCM-001';
        $issue = new Issue();
        $issue->setSummary('Teste de Atividade');
        $issue->setDescription('Descrição do teste de atividade');

        // Salva o issue no Jira
        $this->jiraClient->createIssue($issue);

        // Chama a função trackActivity com um status inválido
        $scrum15 = new Scrum15('https://your-jira-url.com', 'username', 'password');
        $status = 'Invalid Status';
        try {
            $scrum15->trackActivity($issueKey, $status);
            $this->fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            // Verifica se a exceção foi lançada corretamente
            $this->assertEquals('Invalid Status', $e->getMessage());
        }

        // Remove o issue do Jira (opcional)
        $this->jiraClient->deleteIssue($issueKey);
    }
}