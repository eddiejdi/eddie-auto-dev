<?php

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Exception as JiraException;

class Scrum15Test extends PHPUnit\Framework\TestCase {

    protected $jiraClient;

    public function setUp() {
        // Configurar o cliente de Jira aqui
        $this->jiraClient = new Client('http://your-jira-url', 'username', 'password');
    }

    public function testMonitorarAtividades() {
        // Teste monitorarAtividades com valores válidos
        $issues = $this->jiraClient->searchIssues();
        foreach ($issues as $issue) {
            $this->assertNotEmpty($issue['id']);
            $this->assertNotEmpty($issue['fields']['summary']);
        }
    }

    public function testRegistrarEventos() {
        // Teste registrarEventos com valores válidos
        $eventName = 'Test Event';
        $eventData = ['key' => 'value'];
        try {
            $this->jiraClient->createIssue([
                'fields' => [
                    'project' => ['key' => 'YOUR_PROJECT_KEY'],
                    'summary' => $eventName,
                    'description' => json_encode($eventData),
                    'issuetype' => ['name' => 'Task']
                ]
            ]);
        } catch (JiraException $e) {
            $this->fail("Error registering event: " . $e->getMessage());
        }
    }

    public function testMonitorarAtividadesErro() {
        // Teste monitorarAtividades com erro
        try {
            $issues = $this->jiraClient->searchIssues('nonexistent');
        } catch (JiraException $e) {
            $this->assertEquals(JiraException::ERROR_NOT_FOUND, $e->getCode());
        }
    }

    public function testRegistrarEventosErro() {
        // Teste registrarEventos com erro
        try {
            $eventName = 'Test Event';
            $eventData = ['key' => 'value'];
            $this->jiraClient->createIssue([
                'fields' => [
                    'project' => ['key' => 'nonexistent'],
                    'summary' => $eventName,
                    'description' => json_encode($eventData),
                    'issuetype' => ['name' => 'Task']
                ]
            ]);
        } catch (JiraException $e) {
            $this->assertEquals(JiraException::ERROR_NOT_FOUND, $e->getCode());
        }
    }

    public function testMonitorarAtividadesEdgeCase() {
        // Teste monitorarAtividades com edge case
        try {
            $issues = $this->jiraClient->searchIssues('');
        } catch (JiraException $e) {
            $this->assertEquals(JiraException::ERROR_NOT_FOUND, $e->getCode());
        }
    }

    public function testRegistrarEventosEdgeCase() {
        // Teste registrarEventos com edge case
        try {
            $eventName = 'Test Event';
            $eventData = ['key' => 'value'];
            $this->jiraClient->createIssue([
                'fields' => [
                    'project' => ['key' => 'YOUR_PROJECT_KEY'],
                    'summary' => $eventName,
                    'description' => json_encode($eventData),
                    'issuetype' => ['name' => 'Task']
                ]
            ]);
        } catch (JiraException $e) {
            $this->assertEquals(JiraException::ERROR_NOT_FOUND, $e->getCode());
        }
    }

    public function tearDown() {
        // Limpar o cliente de Jira aqui
    }
}