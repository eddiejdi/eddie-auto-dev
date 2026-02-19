<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    public function testCreateTask() {
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'New Task';
        $description = 'This is a new task created by the PHP Agent.';
        $task = createTask($projectKey, $summary, $description);
        $this->assertNotEmpty($task['taskId']);
    }

    public function testUpdateTask() {
        $taskId = 'YOUR_TASK_ID';
        $updatedSummary = 'Updated Task Summary';
        $updatedDescription = 'This task has been updated by the PHP Agent.';
        $updatedTask = updateTask($taskId, $updatedSummary, $updatedDescription);
        $this->assertNotEmpty($updatedTask['taskId']);
    }

    public function testDeleteTask() {
        $deleteTaskId = 'YOUR_TASK_ID';
        $deleteResponse = deleteTask($deleteTaskId);
        $this->assertEquals('Task deleted successfully', $deleteResponse);
    }
}