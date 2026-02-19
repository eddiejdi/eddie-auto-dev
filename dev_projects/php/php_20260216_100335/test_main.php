<?php

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraTrackerTest extends PHPUnit\Framework\TestCase {
    private $jiraClient;

    protected function setUp(): void {
        // Configurações do Jira
        $this->url = 'http://your-jira-instance.com';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Instanciar a classe JiraTracker
        $this->jiraClient = new JiraClient($this->url, $this->username, $this->password);
    }

    public function testCreateIssue() {
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'Teste de Integração PHP Agent com Jira';
        $description = 'Este é um teste para integrar o PHP Agent com o Jira.';
        $issue = $this->jiraClient->createIssue($projectKey, $summary, $description);

        // Verificar se a tarefa foi criada corretamente
        $this->assertNotEmpty($issue['id'], 'Tarefa não criada');
    }

    public function testCreateIssueWithInvalidData() {
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = '';
        $description = 'Este é um teste para integrar o PHP Agent com o Jira.';
        $this->expectException(\InvalidArgumentException::class);
        $this->jiraClient->createIssue($projectKey, $summary, $description);
    }

    public function testUpdateIssue() {
        $issueId = 12345; // ID da tarefa existente
        $updateData = [
            'fields' => [
                'status' => ['name' => 'In Progress']
            ]
        ];
        $updatedIssue = $this->jiraClient->updateIssue($issueId, $updateData);

        // Verificar se a tarefa foi atualizada corretamente
        $this->assertNotEmpty($updatedIssue['id'], 'Tarefa não atualizada');
    }

    public function testUpdateIssueWithInvalidData() {
        $issueId = 12345; // ID da tarefa existente
        $updateData = [
            'fields' => [
                'status' => ['name' => 'In Progress']
            ]
        ];
        $this->expectException(\InvalidArgumentException::class);
        $this->jiraClient->updateIssue($issueId, $updateData);
    }
}