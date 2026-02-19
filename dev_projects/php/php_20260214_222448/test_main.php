<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {

    public function testCreateJiraClient() {
        $this->assertTrue(true);
    }

    public function testTrackActivity() {
        // Test with valid inputs
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';
        $issueKey = 'YOUR-ISSUE-Key';

        $this->assertTrue(trackActivity(new \PhpAgent\Client($jiraUrl, $jiraUsername, $jiraPassword), $issueKey, 'This is a test activity'));

        // Test with invalid inputs
        $this->assertFalse(trackActivity(new \PhpAgent\Client('https://invalid-url.atlassian.net', $jiraUsername, $jiraPassword), $issueKey, 'This is a test activity'));
    }

    public function testMain() {
        // Test the main function with valid inputs
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';
        $issueKey = 'YOUR-ISSUE-Key';

        $this->assertTrue(main());

        // Test the main function with invalid inputs
        $this->assertFalse(main());
    }
}