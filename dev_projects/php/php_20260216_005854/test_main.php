<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    public function testLogActivitySuccess() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $agent = new PHPAgent($jiraUrl, $username, $password);

        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $description = 'The task was completed successfully';

        $this->assertTrue($agent->logActivity($issueKey, $activityType, $description));
    }

    public function testLogActivityError() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $agent = new PHPAgent($jiraUrl, $username, $password);

        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $description = '';

        $this->assertFalse($agent->logActivity($issueKey, $activityType, $description));
    }
}