<?php

use PHPUnit\Framework\TestCase;

class PhpAgentJiraTest extends TestCase {
    public function testCreateTicketSuccess() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $phpAgentJira = new PhpAgentJira($jiraUrl, $username, $password);

        $summary = "Teste de PHP Agent com Jira";
        $description = "Este é um teste para verificar a integração do PHP Agent com Jira.";

        $ticket = $phpAgentJira->createTicket($summary, $description);

        $this->assertArrayHasKey('id', $ticket);
    }

    public function testCreateTicketError() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $phpAgentJira = new PhpAgentJira($jiraUrl, $username, $password);

        // Teste com uma descrição vazia
        $summary = "Teste de PHP Agent com Jira";
        $description = "";

        try {
            $ticket = $phpAgentJira->createTicket($summary, $description);
            $this->fail("Deveria lançar exceção");
        } catch (Exception $e) {
            // Verificar se a exceção é do tipo esperado
            $this->assertInstanceOf(\InvalidArgumentException::class, $e);
        }
    }

    public function testCreateTicketEdgeCase() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $phpAgentJira = new PhpAgentJira($jiraUrl, $username, $password);

        // Teste com um valor inválido para o campo "issuetype"
        $summary = "Teste de PHP Agent com Jira";
        $description = "Este é um teste para verificar a integração do PHP Agent com Jira.";
        $issueType = "InvalidType";

        try {
            $ticket = $phpAgentJira->createTicket($summary, $description, $issueType);
            $this->fail("Deveria lançar exceção");
        } catch (Exception $e) {
            // Verificar se a exceção é do tipo esperado
            $this->assertInstanceOf(\InvalidArgumentException::class, $e);
        }
    }
}