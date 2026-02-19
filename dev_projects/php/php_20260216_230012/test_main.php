<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {
    private $scrum15;

    protected function setUp(): void {
        $this->scrum15 = new Scrum15('http://your-jira-url', 'your-username', 'your-password');
    }

    public function testSetIssueId() {
        $issueId = 'ABC-123';
        $this->scrum15->setIssueId($issueId);
        $this->assertEquals($issueId, $this->scrum15->getIssueId());
    }

    public function testTrackActivitySuccess() {
        // Simular uma tarefa com atividades
        $activityData = [
            ['name' => 'Task 1', 'status' => 'In Progress'],
            ['name' => 'Task 2', 'status' => 'Completed']
        ];

        // Mockar a resposta da API do Jira
        $this->mockJiraApi($activityData);

        $result = $this->scrum15->trackActivity();
        $this->assertEquals(count($result), count($activityData));
    }

    public function testTrackActivityError() {
        // Simular um erro na API do Jira (por exemplo, falha de conexão)
        $this->mockJiraApi(null);

        try {
            $this->scrum15->trackActivity();
            $this->fail('Expected an exception to be thrown');
        } catch (Exception $e) {
            $this->assertEquals($e->getMessage(), 'Error tracking activity: null');
        }
    }

    private function mockJiraApi($activityData) {
        // Simular a resposta da API do Jira
        $response = json_encode(['issues' => $activityData]);
        $this->scrum15->jiraClient->mockResponse($response);
    }
}