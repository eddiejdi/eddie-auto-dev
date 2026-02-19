<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    private $jiraClient;
    private $issueId;

    public function setUp() {
        $this->jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-jira-token');
        $this->issueId = 12345;
    }

    public function testMonitorActivitySuccess() {
        // Simular a criação de um novo issue no Jira
        $this->jiraClient->createIssue('SCRUM-15', 'Task', ['summary' => 'Teste de monitoramento']);

        // Simular a execução do método monitorActivity
        $phpAgent = new PHPAgent($this->jiraUrl, $this->jiraToken, $this->issueId);
        $result = $phpAgent->monitorActivity();

        // Assertar que o método monitorActivity retorne uma mensagem de sucesso
        $this->assertStringContains('Monitoramento iniciado', $result);
    }

    public function testMonitorActivityError() {
        // Simular um erro na criação do issue no Jira (exemplo: divisão por zero)
        $this->jiraClient->createIssue('SCRUM-15', 'Task', ['summary' => 'Teste de monitoramento']);

        // Simular a execução do método monitorActivity
        $phpAgent = new PHPAgent($this->jiraUrl, $this->jiraToken, $this->issueId);
        $result = $phpAgent->monitorActivity();

        // Assertar que o método monitorActivity retorne uma mensagem de erro
        $this->assertStringContains('Erro ao criar issue', $result);
    }
}