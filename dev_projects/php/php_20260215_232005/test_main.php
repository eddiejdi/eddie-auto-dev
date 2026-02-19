<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    public function testCreateIssueSuccess() {
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        try {
            $issueId = $jira->createIssue('YOUR_PROJECT_KEY', 'Task Summary', 'This is a test task.');
            $this->assertNotEmpty($issueId, "Issue ID should not be empty");
        } catch (Exception $e) {
            $this->fail("Failed to create issue: " . $e->getMessage());
        }
    }

    public function testCreateIssueError() {
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        try {
            $issueId = $jira->createIssue('', '', '');
            $this->fail("Failed to create issue with empty values");
        } catch (Exception $e) {
            $this->assertStringContains('Invalid project key', $e->getMessage());
        }
    }

    public function testCreateIssueEdgeCase() {
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        try {
            $issueId = $jira->createIssue(null, '', '');
            $this->fail("Failed to create issue with null values");
        } catch (Exception $e) {
            $this->assertStringContains('Invalid project key', $e->getMessage());
        }
    }
}