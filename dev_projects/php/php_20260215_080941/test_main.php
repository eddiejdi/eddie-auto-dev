<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    private $agent;

    public function setUp() {
        // Create an instance of PHPAgent for testing
        $this->agent = new PHPAgent('https://your-jira-instance.com', 'username', 'password');
    }

    public function testTrackActivitySuccess() {
        // Set up the necessary environment (e.g., issue ID)
        $_GET['issueId'] = 'JIRA-123';

        // Call the method to be tested
        $this->agent->trackActivity();

        // Assert that the activity log file was created and contains the expected content
        $activityLogContent = file_get_contents('activity.log');
        $this->assertStringContains($this->agent->issueId . ': ' . $this->agent->issue->fields->summary, $activityLogContent);
    }

    public function testTrackActivityError() {
        // Set up the necessary environment (e.g., invalid issue ID)
        $_GET['issueId'] = 'INVALID-ID';

        // Call the method to be tested
        try {
            $this->agent->trackActivity();
        } catch (Exception $e) {
            // Assert that an exception was thrown with the expected message
            $this->assertEquals("Error tracking activity: Invalid issue ID", $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Set up the necessary environment (e.g., null or empty issue ID)
        $_GET['issueId'] = null;

        // Call the method to be tested
        try {
            $this->agent->trackActivity();
        } catch (Exception $e) {
            // Assert that an exception was thrown with the expected message
            $this->assertEquals("Issue ID not provided", $e->getMessage());
        }
    }
}