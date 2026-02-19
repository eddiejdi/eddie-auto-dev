<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    public function testLogActivity() {
        $jiraClient = new JiraClient();
        $activityLog = "PHP Agent integrado com Jira";

        try {
            $jiraClient->logActivity($activityLog);
            $this->assertTrue(true, 'Log activity should be successful');
        } catch (Exception $e) {
            $this->assertEquals("Erro: " . $e->getMessage(), 'Error logging activity', 'Expected error message');
        }
    }

    public function testLogActivityWithInvalidData() {
        $jiraClient = new JiraClient();
        $activityLog = null;

        try {
            $jiraClient->logActivity($activityLog);
            $this->fail('Log activity should throw an exception for invalid data');
        } catch (Exception $e) {
            $this->assertEquals("Erro: " . $e->getMessage(), 'Error logging activity with invalid data', 'Expected error message');
        }
    }
}

class ActivityLoggerTest extends TestCase {
    public function testLogActivity() {
        $activityLogger = new ActivityLogger();
        $activityLog = "PHP Agent integrado com Jira";

        try {
            $activityLogger->logActivity($activityLog);
            $this->assertTrue(true, 'Log activity should be successful');
        } catch (Exception $e) {
            $this->assertEquals("Erro: " . $e->getMessage(), 'Error logging activity', 'Expected error message');
        }
    }

    public function testLogActivityWithInvalidData() {
        $activityLogger = new ActivityLogger();
        $activityLog = null;

        try {
            $activityLogger->logActivity($activityLog);
            $this->fail('Log activity should throw an exception for invalid data');
        } catch (Exception $e) {
            $this->assertEquals("Erro: " . $e->getMessage(), 'Error logging activity with invalid data', 'Expected error message');
        }
    }
}