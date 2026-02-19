<?php

use PHPUnit\Framework\TestCase;
use App\JiraClient;
use App\Log;

class MainTest extends TestCase {
    public function testCreateIssue() {
        // Mock the Jira client and log objects
        $jiraClientMock = $this->createMock(JiraClient::class);
        $logMock = $this->createMock(Log::class);

        // Create an instance of the Main class with mocked dependencies
        $main = new Main($jiraClientMock, $logMock);

        // Define test data
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in';

        // Set up expectations for the Jira client and log methods
        $jiraClientMock->expects($this->once())
            ->method('createIssue')
            ->with($issueKey, $activityDescription)
            ->willReturn(true);

        $logMock->expects($this->once())
            ->method('info')
            ->with('Activity tracked successfully');

        // Call the main method
        $main->main();

        // Assert that the Jira client and log methods were called as expected
        $jiraClientMock->verify();
        $logMock->verify();
    }

    public function testCreateIssueError() {
        // Mock the Jira client and log objects
        $jiraClientMock = $this->createMock(JiraClient::class);
        $logMock = $this->createMock(Log::class);

        // Create an instance of the Main class with mocked dependencies
        $main = new Main($jiraClientMock, $logMock);

        // Define test data
        $issueKey = 'ABC-123';
        $activityDescription = '';

        // Set up expectations for the Jira client and log methods
        $jiraClientMock->expects($this->once())
            ->method('createIssue')
            ->with($issueKey, $activityDescription)
            ->willThrowException(new Exception('Invalid activity description'));

        $logMock->expects($this->once())
            ->method('error')
            ->with('Failed to track activity: Invalid activity description');

        // Call the main method
        $main->main();

        // Assert that the Jira client and log methods were called as expected
        $jiraClientMock->verify();
        $logMock->verify();
    }
}