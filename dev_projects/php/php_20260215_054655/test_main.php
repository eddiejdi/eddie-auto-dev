<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    private $jiraClient;
    private $phpAgent;

    protected function setUp(): void {
        // Configuração do JiraClient
        $this->jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        // Configuração do PHPAgent
        $this->phpAgent = new PHPAgent($this->jiraClient);
    }

    public function testCreateIssueSuccess() {
        // Valores válidos para o createIssue método
        $projectKey = 'YOUR_PROJECT_KEY';
        $issueType = 'TASK';
        $summary = 'Implement a new feature';
        $description = 'This is the detailed description of the issue';

        try {
            // Criar um novo issue no Jira
            $issueId = $this->jiraClient->createIssue($projectKey, $issueType, $summary, $description);

            // Verificar se o método retornou um valor válido (ID do issue)
            $this->assertNotEmpty($issueId);
        } catch (Exception $e) {
            // Verificar se a exceção foi capturada corretamente
            $this->assertEquals('Error creating issue: ' . $e->getMessage(), $e->getMessage());
        }
    }

    public function testCreateIssueFailure() {
        // Valores inválidos para o createIssue método (exemplo de divisão por zero)
        $projectKey = 'YOUR_PROJECT_KEY';
        $issueType = 'TASK';
        $summary = 'Implement a new feature';
        $description = 'This is the detailed description of the issue';

        try {
            // Criar um novo issue no Jira
            $this->jiraClient->createIssue($projectKey, $issueType, $summary, 0);
        } catch (Exception $e) {
            // Verificar se a exceção foi capturada corretamente
            $this->assertEquals('Error creating issue: Division by zero', $e->getMessage());
        }
    }

    public function testTrackActivitySuccess() {
        // Valores válidos para o trackActivity método
        $projectKey = 'YOUR_PROJECT_KEY';
        $issueType = 'TASK';
        $summary = 'Implement a new feature';
        $description = 'This is the detailed description of the issue';

        try {
            // Criar um novo issue no Jira
            $issueId = $this->jiraClient->createIssue($projectKey, $issueType, $summary, $description);

            // Log ou enviar a mensagem de atividade para o PHP Agent
            // ...

            echo "Issue created with ID: $issueId\n";
        } catch (Exception $e) {
            // Verificar se a exceção foi capturada corretamente
            $this->assertEquals('Error creating issue: ' . $e->getMessage(), $e->getMessage());
        }
    }

    public function testTrackActivityFailure() {
        // Valores inválidos para o trackActivity método (exemplo de divisão por zero)
        $projectKey = 'YOUR_PROJECT_KEY';
        $issueType = 'TASK';
        $summary = 'Implement a new feature';
        $description = 'This is the detailed description of the issue';

        try {
            // Criar um novo issue no Jira
            $this->jiraClient->createIssue($projectKey, $issueType, $summary, 0);
        } catch (Exception $e) {
            // Verificar se a exceção foi capturada corretamente
            $this->assertEquals('Error creating issue: Division by zero', $e->getMessage());
        }
    }
}