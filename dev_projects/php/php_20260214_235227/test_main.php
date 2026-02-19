<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    private $jiraClient;

    protected function setUp(): void {
        $this->jiraClient = new PHPAgent('https://your-jira-url.com', 'username', 'password');
    }

    public function testCreateIssueSuccess() {
        $issueData = [
            'summary' => 'Test Issue',
            'description' => 'This is a test issue created by the PHP Agent.',
            'priority' => 'High',
            'assignee' => 'user123'
        ];

        $result = $this->jiraClient->createIssue($issueData);
        $this->assertEquals("Issue created successfully", $result);
    }

    public function testCreateIssueError() {
        $issueData = [
            'summary' => '',
            'description' => 'This is a test issue created by the PHP Agent.',
            'priority' => 'High',
            'assignee' => 'user123'
        ];

        try {
            $this->jiraClient->createIssue($issueData);
        } catch (\Exception $e) {
            $this->assertEquals("Error creating issue: Invalid summary", $e->getMessage());
        }
    }

    public function testUpdateIssueSuccess() {
        $issueId = 123;
        $issueData = [
            'summary' => 'Updated Test Issue',
            'description' => 'This is an updated test issue created by the PHP Agent.',
            'priority' => 'High',
            'assignee' => 'user123'
        ];

        $result = $this->jiraClient->updateIssue($issueId, $issueData);
        $this->assertEquals("Issue updated successfully", $result);
    }

    public function testUpdateIssueError() {
        $issueId = 123;
        $issueData = [
            'summary' => '',
            'description' => 'This is an updated test issue created by the PHP Agent.',
            'priority' => 'High',
            'assignee' => 'user123'
        ];

        try {
            $this->jiraClient->updateIssue($issueId, $issueData);
        } catch (\Exception $e) {
            $this->assertEquals("Error updating issue: Invalid summary", $e->getMessage());
        }
    }

    public function testDeleteIssueSuccess() {
        $issueId = 123;

        $result = $this->jiraClient->deleteIssue($issueId);
        $this->assertEquals("Issue deleted successfully", $result);
    }

    public function testDeleteIssueError() {
        $issueId = 123;

        try {
            $this->jiraClient->deleteIssue($issueId);
        } catch (\Exception $e) {
            $this->assertEquals("Error deleting issue: Invalid issue ID", $e->getMessage());
        }
    }
}