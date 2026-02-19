<?php

use PHPUnit\Framework\TestCase;

class TaskTrackerTest extends TestCase {
    private $taskTracker;

    public function setUp(): void {
        // Configurações do PHP Agent
        $agentConfig = [
            'host' => 'localhost',
            'port' => 2000,
            'username' => 'YOUR_AGENT_USERNAME',
            'password' => 'YOUR_AGENT_PASSWORD'
        ];

        // Configurações do Jira API
        $jiraConfig = [
            'url' => 'https://your-jira-instance.atlassian.net/rest/api/3',
            'username' => 'YOUR_JIRA_USERNAME',
            'password' => 'YOUR_JIRA_PASSWORD'
        ];

        // Criar instância da classe TaskTracker
        $this->taskTracker = new TaskTracker($agentConfig, $jiraConfig);
    }

    public function testAddTask() {
        $title = 'Teste Tarefa';
        $description = 'Descrição da tarefa';

        try {
            $response = $this->taskTracker->addTask($title, $description);
            $this->assertNotEmpty($response['id'], "Task ID should not be empty");
        } catch (\Exception $e) {
            $this->fail("Error adding task: " . $e->getMessage());
        }
    }

    public function testUpdateTask() {
        $taskId = 12345;
        $title = 'Novo Título';
        $description = 'Nova descrição da tarefa';

        try {
            $response = $this->taskTracker->updateTask($taskId, $title, $description);
            $this->assertNotEmpty($response['id'], "Task ID should not be empty");
        } catch (\Exception $e) {
            $this->fail("Error updating task: " . $e->getMessage());
        }
    }

    public function testDeleteTask() {
        $taskId = 12345;

        try {
            $response = $this->taskTracker->deleteTask($taskId);
            $this->assertNotEmpty($response['id'], "Task ID should not be empty");
        } catch (\Exception $e) {
            $this->fail("Error deleting task: " . $e->getMessage());
        }
    }

    public function testListTasks() {
        try {
            $response = $this->taskTracker->listTasks();
            $this->assertNotEmpty($response['issues'], "No tasks should be listed");
        } catch (\Exception $e) {
            $this->fail("Error listing tasks: " . $e->getMessage());
        }
    }

    public function testAddTaskWithInvalidTitle() {
        $title = '';
        $description = 'Descrição da tarefa';

        try {
            $response = $this->taskTracker->addTask($title, $description);
            $this->fail("Error should be thrown for invalid title");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testAddTaskWithInvalidDescription() {
        $title = 'Teste Tarefa';
        $description = '';

        try {
            $response = $this->taskTracker->addTask($title, $description);
            $this->fail("Error should be thrown for invalid description");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testUpdateTaskWithInvalidId() {
        $taskId = 0;
        $title = 'Novo Título';
        $description = 'Nova descrição da tarefa';

        try {
            $response = $this->taskTracker->updateTask($taskId, $title, $description);
            $this->fail("Error should be thrown for invalid task ID");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testUpdateTaskWithInvalidTitle() {
        $taskId = 12345;
        $title = '';
        $description = 'Nova descrição da tarefa';

        try {
            $response = $this->taskTracker->updateTask($taskId, $title, $description);
            $this->fail("Error should be thrown for invalid title");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testUpdateTaskWithInvalidDescription() {
        $taskId = 12345;
        $title = 'Novo Título';
        $description = '';

        try {
            $response = $this->taskTracker->updateTask($taskId, $title, $description);
            $this->fail("Error should be thrown for invalid description");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testDeleteTaskWithInvalidId() {
        $taskId = 0;

        try {
            $response = $this->taskTracker->deleteTask($taskId);
            $this->fail("Error should be thrown for invalid task ID");
        } catch (\Exception $e) {
            // Expected exception
        }
    }

    public function testListTasksWithInvalidQuery() {
        try {
            $response = $this->taskTracker->listTasks('invalid_query');
            $this->fail("Error should be thrown for invalid query");
        } catch (\Exception $e) {
            // Expected exception
        }
    }
}