<?php

use PHPUnit\Framework\TestCase;

class TaskManagerTest extends TestCase {
    public function testCreateTask() {
        $taskManager = new TaskManager();
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'Implement PHP Agent with Jira';
        $description = 'Track tasks using PHP Agent and Jira API';

        $response = $taskManager->createTask($projectKey, $summary, $description);
        $this->assertNotEmpty($response['key']);
        $this->assertEquals('Bug', $response['fields']['issuetype']['name']);
    }

    public function testUpdateTask() {
        $taskManager = new TaskManager();
        $issueKey = 'YOUR_TASK_KEY';
        $summary = 'Implement PHP Agent with Jira';
        $description = 'Update task details using PHP Agent and Jira API';

        $response = $taskManager->updateTask($issueKey, $summary, $description);
        $this->assertNotEmpty($response['key']);
        $this->assertEquals('Bug', $response['fields']['issuetype']['name']);
    }

    public function testDeleteTask() {
        $taskManager = new TaskManager();
        $issueKey = 'YOUR_TASK_KEY';

        $response = $taskManager->deleteTask($issueKey);
        $this->assertEmpty($response);
    }
}