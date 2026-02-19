<?php

use PHPUnit\Framework\TestCase;

class TaskTrackerTest extends TestCase {
    public function setUp() {
        $this->jiraConnector = new JiraConnector();
        $this->scrumBoard = new ScrumBoard('https://your-jira-url.com', 'username', 'password');
        $this->taskTracker = new TaskTracker($this->jiraConnector, $this->scrumBoard);
    }

    public function testTrackTaskSuccess() {
        $taskId = 123;
        $status = 'In Progress';
        $result = $this->taskTracker->trackTask($taskId, $status);
        $this->assertEquals("Tarefa {$taskId} atualizada para {$status}", $result);
    }

    public function testTrackTaskInvalidStatus() {
        $taskId = 123;
        $status = 'Invalid';
        $result = $this->taskTracker->trackTask($taskId, $status);
        $this->assertEquals("Falha ao atualizar o status da tarefa {$taskId}: Status inválido", $result);
    }

    public function testTrackTaskJiraConnectorException() {
        $this->expectException(Exception::class);
        $taskId = 123;
        $status = 'In Progress';
        // Simula um erro em JiraConnector
        $this->jiraConnector->updateTaskStatus = function($taskId, $status) {
            throw new Exception("Erro ao atualizar o status da tarefa {$taskId}");
        };
        $result = $this->taskTracker->trackTask($taskId, $status);
    }
}