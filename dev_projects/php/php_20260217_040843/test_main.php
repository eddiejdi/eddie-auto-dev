<?php

use PHPUnit\Framework\TestCase;
use Jira\Client;

class PhpAgentTest extends TestCase {
    private $jiraClient;

    public function setUp() {
        // Configuração do Jira Client
        $this->jiraClient = new Client('https://your-jira-instance.com');
        $this->jiraClient->login('your-username', 'your-password');
    }

    public function testCreateIssueSuccess() {
        $summary = "Test Issue";
        $description = "This is a test issue description.";
        $expectedId = 12345; // Simulando um ID de.issue válido

        $this->jiraClient->createIssue($summary, $description);

        // Verifica se o método createIssue retornou o ID do issue
        $this->assertEquals($expectedId, $this->jiraClient->getLastCreatedIssueId());
    }

    public function testCreateIssueFailure() {
        $summary = "Test Issue";
        $description = ""; // String vazia

        try {
            $this->jiraClient->createIssue($summary, $description);
            $this->fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            // Verifica se o erro é do tipo Jira\JiraException
            $this->assertInstanceOf(Jira\JiraException::class, $e);
            $this->assertEquals('Invalid issue summary', $e->getMessage());
        }
    }

    public function testLogEventSuccess() {
        $eventName = "PHP Agent Log";
        $eventDescription = "This is a log event from the PHP Agent.";
        $expectedId = 67890; // Simulando um ID de.log válido

        $this->jiraClient->logEvent(12345, $eventName, $eventDescription);

        // Verifica se o método logEvent retornou o ID do log
        $this->assertEquals($expectedId, $this->jiraClient->getLastCreatedLogId());
    }

    public function testLogEventFailure() {
        $eventName = "PHP Agent Log";
        $eventDescription = ""; // String vazia

        try {
            $this->jiraClient->logEvent(12345, $eventName, $eventDescription);
            $this->fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            // Verifica se o erro é do tipo Jira\JiraException
            $this->assertInstanceOf(Jira\JiraException::class, $e);
            $this->assertEquals('Invalid log event summary', $e->getMessage());
        }
    }

    public function tearDown() {
        // Limpa as configurações após os testes
        $this->jiraClient = null;
    }
}