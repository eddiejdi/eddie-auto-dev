<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {

    public function setUp() {
        // Configurar o agente PHP Agent
        $this->agent = new Agent([
            'name' => 'PHP Agent',
            'version' => '1.0.0',
        ]);
    }

    public function testCreateTask() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, 'Test Task', 'This is a test task for the PHP Agent.');
        $this->assertNotEmpty($task);
    }

    public function testCreateTaskError() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, '', '');
        $this->assertNull($task);
    }

    public function testListTasks() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $tasks = listTasks($client);
        $this->assertNotEmpty($tasks);
    }

    public function testListTasksError() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $tasks = listTasks(null);
        $this->assertNull($tasks);
    }

    public function testUpdateTask() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, 'Test Task', 'This is a test task for the PHP Agent.');
        if ($task) {
            $updatedTask = updateTask($client, $task['key'], 'Updated Test Task', 'This is an updated test task for the PHP Agent.');
            $this->assertNotEmpty($updatedTask);
        }
    }

    public function testUpdateTaskError() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, '', '');
        if ($task) {
            $updatedTask = updateTask($client, $task['key'], '', '');
            $this->assertNull($updatedTask);
        }
    }

    public function testDeleteTask() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, 'Test Task', 'This is a test task for the PHP Agent.');
        if ($task) {
            $deletedTask = deleteTask($client, $task['key']);
            $this->assertNotEmpty($deletedTask);
        }
    }

    public function testDeleteTaskError() {
        $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
        $task = createTask($client, '', '');
        if ($task) {
            $deletedTask = deleteTask($client, '');
            $this->assertNull($deletedTask);
        }
    }
}