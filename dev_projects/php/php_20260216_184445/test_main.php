<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase
{
    public function testStartPhpAgent()
    {
        $this->assertTrue(PhpAgent::start());
    }

    public function testSendToJiraSuccess()
    {
        $issueKey = 'YOUR_ISSUE_KEY';
        $summary = 'Activity: Processamento de dados';
        $description = 'Description of the activity';

        $response = sendToJira($issueKey, $summary, $description);
        $this->assertNotEmpty($response);
    }

    public function testSendToJiraError()
    {
        $issueKey = 'YOUR_ISSUE_KEY';
        $summary = '';
        $description = '';

        try {
            sendToJira($issueKey, $summary, $description);
        } catch (Exception $e) {
            $this->assertEquals('Failed to create issue.', $e->getMessage());
        }
    }

    public function testMainFunction()
    {
        $this->assertTrue(main());
    }
}