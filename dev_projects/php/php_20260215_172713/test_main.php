<?php

use PHPUnit\Framework\TestCase;

class TaskTrackerTest extends TestCase {
    private $taskTracker;

    protected function setUp() {
        $this->taskTracker = new TaskTracker('https://your-jira-instance.atlassian.net', 'username', 'password');
    }

    public function testAddTaskWithValidData() {
        // Caso de sucesso com valores válidos
        $title = 'Implement SCRUM-15 in PHP';
        $status = 'In Progress';
        $assignee = 'John Doe';

        $task = $this->taskTracker->addTask($title, $status, $assignee);

        $this->assertNotEmpty($task->getId());
        $this->assertEquals($title, $task->getTitle());
        $this->assertEquals($status, $task->getStatus());
        $this->assertEquals($assignee, $task->getAssignee());
    }

    public function testAddTaskWithInvalidData() {
        // Caso de erro (divisão por zero)
        $this->expectException(\InvalidArgumentException::class);
        $this->taskTracker->addTask('Implement SCRUM-15 in PHP', 'In Progress', null);
    }
}