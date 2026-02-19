<?php

use PHPUnit\Framework\TestCase;

class JiraApiTest extends TestCase {

    public function testAuthenticate() {
        $this->expectException(Exception::class);
        authenticate(JIRA_API_URL, 'invalid-username', 'invalid-password');
    }

    public function testCreateTask() {
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        try {
            createTask(JIRA_API_URL, $session, 'T123', 'Implement PHP Agent for Laravel and Symfony', 'This task is about integrating PHP Agent with Jira for tracking activities in PHP projects.');
        } catch (Exception $e) {
            $this->assertEquals('Failed to create task: Invalid session token', $e->getMessage());
        }
    }

    public function testUpdateTask() {
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        try {
            updateTask(JIRA_API_URL, $session, 'T123', 'Implement PHP Agent for Laravel and Symfony', 'This task is about integrating PHP Agent with Jira for tracking activities in PHP projects.');
        } catch (Exception $e) {
            $this->assertEquals('Failed to update task: Invalid session token', $e->getMessage());
        }
    }

    public function testGetTask() {
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        try {
            getTask(JIRA_API_URL, $session, 'T123');
        } catch (Exception $e) {
            $this->assertEquals('Failed to get task: Invalid session token', $e->getMessage());
        }
    }

    public function testListTasks() {
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        try {
            listTasks(JIRA_API_URL, $session);
        } catch (Exception $e) {
            $this->assertEquals('Failed to list tasks: Invalid session token', $e->getMessage());
        }
    }

    public function testDeleteTask() {
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        try {
            deleteTask(JIRA_API_URL, $session, 'T123');
        } catch (Exception $e) {
            $this->assertEquals('Failed to delete task: Invalid session token', $e->getMessage());
        }
    }
}