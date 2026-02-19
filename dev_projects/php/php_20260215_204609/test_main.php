<?php

use PHPUnit\Framework\TestCase;
use Jira\JiraClient;
use Jira\Api\ClientException;

class JiraIntegrationTest extends TestCase {
    private $jiraClient;

    public function setUp() {
        // Configurações do Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->jiraUsername = 'your-username';
        $this->jiraPassword = 'your-password';

        // Instanciar a classe JiraIntegration
        $this->jiraClient = new JiraIntegration($this->jiraUrl, $this->jiraUsername, $this->jiraPassword);
    }

    public function testCreateIssue() {
        $projectKey = 'NEW-123';
        $summary = 'Teste de criação de issue';
        $description = 'Descrição do teste.';
        $createdIssue = $this->jiraClient->createIssue($projectKey, $summary, $description);
        $this->assertNotEmpty($createdIssue['key'], 'Issue criado com sucesso');
    }

    public function testCreateIssueWithInvalidData() {
        $projectKey = 'NEW-123';
        $summary = '';
        $description = 'Descrição do teste.';
        $this->expectException(ClientException::class);
        $this->jiraClient->createIssue($projectKey, $summary, $description);
    }

    public function testUpdateIssue() {
        $issueKey = 'NEW-123';
        $updatedSummary = 'Teste de atualização de issue';
        $updatedDescription = 'Descrição atualizada do teste.';
        $jiraClient->createIssue('NEW-456', 'Teste de criação de issue 2', 'Descrição do teste 2');
        $response = $this->jiraClient->updateIssue($issueKey, $updatedSummary, $updatedDescription);
        $this->assertNotEmpty($response['key'], 'Issue atualizado com sucesso');
    }

    public function testUpdateIssueWithInvalidData() {
        $issueKey = 'NEW-123';
        $summary = '';
        $description = 'Descrição do teste.';
        $this->expectException(ClientException::class);
        $this->jiraClient->updateIssue($issueKey, $summary, $description);
    }

    public function testGetIssue() {
        $issueKey = 'NEW-123';
        $response = $this->jiraClient->getIssue($issueKey);
        $this->assertNotEmpty($response['key'], 'Issue obtido com sucesso');
    }

    public function testCloseIssue() {
        $issueKey = 'NEW-123';
        $response = $this->jiraClient->closeIssue($issueKey);
        $this->assertTrue($response, 'Issue fechado com sucesso');
    }

    public function testDeleteIssue() {
        $issueKey = 'NEW-123';
        $response = $this->jiraClient->deleteIssue($issueKey);
        $this->assertTrue($response, 'Issue deletado com sucesso');
    }
}