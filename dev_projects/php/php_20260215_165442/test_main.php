<?php

use PHPUnit\Framework\TestCase;
use Jira\Client;
use Jira\Issue;

class JiraAgentTest extends TestCase {
    private $jiraAgent;

    public function setUp() {
        // Configurações do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o JiraAgent
        $this->jiraAgent = new JiraAgent($url, $username, $password);
    }

    public function testTrackActivitySuccess() {
        // Valores válidos
        $issueKey = 'ABC123';
        $activityType = 'Bug Fix';
        $details = 'Fixed a critical bug in the application';

        try {
            $this->jiraAgent->trackActivity($issueKey, $activityType, $details);
            $this->assertTrue(true); // Verifica se a função não lança exceção
        } catch (Exception $e) {
            $this->fail("Expected no exception but got: {$e->getMessage()}");
        }
    }

    public function testTrackActivityFailureDivideByZero() {
        // Valores inválidos
        $issueKey = 'ABC123';
        $activityType = 'Bug Fix';
        $details = '';

        try {
            $this->jiraAgent->trackActivity($issueKey, $activityType, $details);
            $this->fail("Expected an exception but got: No exception thrown");
        } catch (Exception $e) {
            $this->assertTrue(true); // Verifica se a função lança exceção
        }
    }

    public function testTrackActivityEdgeCaseNullValue() {
        // Edge case: valor nulo
        $issueKey = 'ABC123';
        $activityType = null;
        $details = '';

        try {
            $this->jiraAgent->trackActivity($issueKey, $activityType, $details);
            $this->fail("Expected an exception but got: No exception thrown");
        } catch (Exception $e) {
            $this->assertTrue(true); // Verifica se a função lança exceção
        }
    }

    public function testTrackActivityEdgeCaseEmptyString() {
        // Edge case: string vazia
        $issueKey = 'ABC123';
        $activityType = '';
        $details = '';

        try {
            $this->jiraAgent->trackActivity($issueKey, $activityType, $details);
            $this->fail("Expected an exception but got: No exception thrown");
        } catch (Exception $e) {
            $this->assertTrue(true); // Verifica se a função lança exceção
        }
    }

    public function testTrackActivityEdgeCaseNoneValue() {
        // Edge case: None value
        $issueKey = 'ABC123';
        $activityType = null;
        $details = '';

        try {
            $this->jiraAgent->trackActivity($issueKey, $activityType, $details);
            $this->fail("Expected an exception but got: No exception thrown");
        } catch (Exception $e) {
            $this->assertTrue(true); // Verifica se a função lança exceção
        }
    }
}