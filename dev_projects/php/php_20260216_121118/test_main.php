<?php

use PhpAgent\Agent;
use PhpAgent\Jira;

class JiraTrackerTest extends PHPUnit\Framework\TestCase {
    private $jira;

    protected function setUp(): void {
        // Configurações do Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instancia o JiraTracker
        $this->tracker = new JiraTracker($this->jiraUrl, $username, $password);
    }

    public function testCreateIssue() {
        $issueData = [
            'project' => ['key' => 'YOUR-PROJECT'],
            'summary' => 'Example Issue',
            'description' => 'This is an example issue created using PHP Agent with Jira.',
            'issuetype' => ['name' => 'Bug']
        ];

        try {
            $response = $this->tracker->createIssue($issueData);
            $this->assertNotEmpty($response, "Response should not be empty");
            $this->assertTrue(is_array($response), "Response should be an array");
        } catch (Exception $e) {
            $this->fail("Failed to create issue: " . $e->getMessage());
        }
    }

    public function testCreateIssueError() {
        $issueData = [
            'project' => ['key' => 'YOUR-PROJECT'],
            'summary' => '',
            'description' => '',
            'issuetype' => ['name' => 'Bug']
        ];

        try {
            $this->tracker->createIssue($issueData);
            $this->fail("Expected an exception to be thrown");
        } catch (Exception $e) {
            $this->assertTrue(true, "Exception was thrown as expected");
        }
    }

    public function testUpdateIssue() {
        $issueId = 123; // Assume this is a valid issue ID
        $updateData = [
            'summary' => 'Updated Example Issue',
            'description' => 'This is an updated example issue created using PHP Agent with Jira.'
        ];

        try {
            $response = $this->tracker->updateIssue($issueId, $updateData);
            $this->assertNotEmpty($response, "Response should not be empty");
            $this->assertTrue(is_array($response), "Response should be an array");
        } catch (Exception $e) {
            $this->fail("Failed to update issue: " . $e->getMessage());
        }
    }

    public function testUpdateIssueError() {
        $issueId = 123; // Assume this is a valid issue ID
        $updateData = [
            'summary' => '',
            'description' => ''
        ];

        try {
            $this->tracker->updateIssue($issueId, $updateData);
            $this->fail("Expected an exception to be thrown");
        } catch (Exception $e) {
            $this->assertTrue(true, "Exception was thrown as expected");
        }
    }

    public function testDeleteIssue() {
        $issueId = 123; // Assume this is a valid issue ID

        try {
            $response = $this->tracker->deleteIssue($issueId);
            $this->assertTrue(is_bool($response), "Response should be a boolean");
        } catch (Exception $e) {
            $this->fail("Failed to delete issue: " . $e->getMessage());
        }
    }

    public function testDeleteIssueError() {
        $issueId = 123; // Assume this is a valid issue ID

        try {
            $response = $this->tracker->deleteIssue($issueId);
            $this->assertTrue(is_bool($response), "Response should be a boolean");
        } catch (Exception $e) {
            $this->fail("Expected an exception to be thrown");
        }
    }
}