<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    private $jiraClient;

    public function setUp() {
        // Configurar a URL do Jira e as credenciais de autenticação
        $this->jiraClient = new JiraClient('https://your-jira-instance.atlassian.net', 'username', 'password');
    }

    public function testCreateIssueWithValidData() {
        $issueData = [
            'project' => 'SCRUM-15',
            'summary' => 'Implementar PHP Agent com Jira',
            'description' => 'Tracking de atividades usando PHP Agent e Jira',
            'assignee' => 'username',
            'priority' => 'High'
        ];

        $this->jiraClient->createIssue($issueData);
    }

    public function testCreateIssueWithInvalidData() {
        $issueData = [
            'project' => 'SCRUM-15',
            'summary' => '',
            'description' => null,
            'assignee' => null,
            'priority' => null
        ];

        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verificar se a exceção é do tipo esperado
            $this->assertEquals('Invalid issue data', $e->getMessage());
        }
    }

    public function testCreateSprintWithValidData() {
        $sprintData = [
            'name' => 'Sprint 1',
            'startDate' => '2023-04-01',
            'endDate' => '2023-04-30'
        ];

        $this->jiraClient->createSprint($sprintData);
    }

    public function testCreateSprintWithInvalidData() {
        $sprintData = [
            'name' => '',
            'startDate' => null,
            'endDate' => null
        ];

        try {
            $this->jiraClient->createSprint($sprintData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verificar se a exceção é do tipo esperado
            $this->assertEquals('Invalid sprint data', $e->getMessage());
        }
    }

    public function testCreateTaskWithValidData() {
        $taskData = [
            'summary' => 'Implementar PHP Agent com Jira',
            'description' => 'Tracking de atividades usando PHP Agent e Jira',
            'assignee' => 'username',
            'priority' => 'High'
        ];

        $this->jiraClient->createTask($taskData);
    }

    public function testCreateTaskWithInvalidData() {
        $taskData = [
            'summary' => '',
            'description' => null,
            'assignee' => null,
            'priority' => null
        ];

        try {
            $this->jiraClient->createTask($taskData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verificar se a exceção é do tipo esperado
            $this->assertEquals('Invalid task data', $e->getMessage());
        }
    }
}