<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {

    public function setUp() {
        // Configuração do Jira Client e Activity Tracker
        $this->jiraClient = new \PHPUnit\Framework\MockObject\Stub();
        $this->activityTracker = new \PHPUnit\Framework\MockObject\Stub();

        // Mockar métodos necessários para o teste
        $this->jiraClient->method('updateIssueStatus')->willReturn(true);
        $this->activityTracker->method('addActivity')->willReturn(true);

        // Criar instância do PHPAgent com mocks
        $this->phpAgent = new PHPAgent($this->jiraClient, $this->activityTracker);
    }

    public function testTrackActivityWithValidData() {
        // Configurar dados de teste
        $issueKey = 'ABC-123';
        $activityDescription = 'Realização da tarefa 1/4';

        // Chamar o método trackActivity
        $this->phpAgent->trackActivity($issueKey, $activityDescription);

        // Verificar se os métodos foram chamados corretamente
        $this->assertTrue($this->jiraClient->method('updateIssueStatus')->wasCalled());
        $this->assertTrue($this->activityTracker->method('addActivity')->wasCalled());
    }

    public function testTrackActivityWithInvalidData() {
        // Configurar dados de teste com valores inválidos
        $issueKey = 'ABC-123';
        $activityDescription = '';

        // Chamar o método trackActivity
        $this->phpAgent->trackActivity($issueKey, $activityDescription);

        // Verificar se os métodos foram chamados corretamente
        $this->assertTrue($this->jiraClient->method('updateIssueStatus')->wasCalled());
        $this->assertFalse($this->activityTracker->method('addActivity')->wasCalled());
    }
}