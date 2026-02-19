<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    private $phpAgent;

    protected function setUp(): void {
        // Configuração do PHP Agent
        $url = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Criar um objeto PHPAgent
        $this->phpAgent = new PHPAgent($url, $username, $password);
    }

    public function testTrackActivitySuccess() {
        // Caso de sucesso com valores válidos
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in successfully.';
        $expectedMessage = "Activity tracked successfully.";

        $result = $this->phpAgent->trackActivity($issueKey, $activityDescription);

        $this->assertEquals($expectedMessage, $result);
    }

    public function testTrackActivityError() {
        // Caso de erro (divisão por zero)
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in successfully.';
        $expectedMessage = "Error tracking activity: Division by zero.";

        try {
            $this->phpAgent->trackActivity($issueKey, $activityDescription);
        } catch (Exception $e) {
            $result = $e->getMessage();

            $this->assertEquals($expectedMessage, $result);
        }
    }

    public function testTrackActivityEdgeCase() {
        // Edge case (valores limite)
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in successfully.';
        $expectedMessage = "Activity tracked successfully.";

        $result = $this->phpAgent->trackActivity($issueKey, $activityDescription);

        $this->assertEquals($expectedMessage, $result);
    }
}