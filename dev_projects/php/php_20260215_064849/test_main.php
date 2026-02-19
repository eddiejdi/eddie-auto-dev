<?php

use PhpAgent\Jira\JiraClient;
use PHPUnit\Framework\TestCase;

class JiraIntegrationTest extends TestCase {
    private $jiraClient;

    public function setUp() {
        // Configuração do JiraClient (url, username e password)
        $this->jiraClient = new JiraClient('https://your-jira-instance.com', 'your-username', 'your-password');
    }

    public function testTrackActivitySuccess() {
        // Caso de sucesso com valores válidos
        $issueKey = 'ABC-123';
        $activityDescription = 'This is a test activity';

        $response = $this->jiraClient->createIssueComment($issueKey, $activityDescription);
        $this->assertNotEmpty($response);
    }

    public function testTrackActivityError() {
        // Caso de erro (divisão por zero)
        $issueKey = 'ABC-123';
        $activityDescription = '';

        try {
            $this->jiraClient->createIssueComment($issueKey, $activityDescription);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Activity description cannot be empty', $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Edge case (valores limite, strings vazias, None, etc)
        $issueKey = '';
        $activityDescription = null;

        try {
            $this->jiraClient->createIssueComment($issueKey, $activityDescription);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid issue key or activity description', $e->getMessage());
        }
    }
}