<?php

use GuzzleHttp\Client;
use GuzzleHttp\Exception\RequestException;

class JiraClientTest extends PHPUnit\Framework\TestCase {
    private $jiraUrl = "https://your-jira-instance.atlassian.net";
    private $jiraToken = "your-jira-token";

    protected function setUp(): void {
        $this->client = new Client([
            'base_uri' => $this->jiraUrl,
            'headers' => [
                'Authorization' => "Bearer $this->jiraToken",
                'Content-Type' => 'application/json',
            ],
        ]);
    }

    public function testCreateIssue() {
        // Test case for creating an issue
        $fields = [
            'project' => ['key' => 'SCRUM'],
            'summary' => 'Test Issue',
            'description' => 'This is a test issue.',
            'issuetype' => ['name' => 'Bug'],
        ];

        $response = $this->client->post("/rest/api/2/issue", [
            'json' => [
                'fields' => $fields,
            ],
        ]);

        $this->assertEquals(201, $response->getStatusCode());
    }

    public function testCreateIssueWithInvalidFields() {
        // Test case for creating an issue with invalid fields
        $fields = [
            'project' => ['key' => 'SCRUM'],
            'summary' => '',
            'description' => '',
            'issuetype' => ['name' => 'Bug'],
        ];

        try {
            $response = $this->client->post("/rest/api/2/issue", [
                'json' => [
                    'fields' => $fields,
                ],
            ]);
        } catch (RequestException $e) {
            $this->assertEquals(400, $e->getResponse()->getStatusCode());
        }
    }

    public function testGetIssue() {
        // Test case for getting an issue
        $issueKey = "SCRUM-15";

        try {
            $response = $this->client->get("/rest/api/2/issue/$issueKey");

            $this->assertEquals(200, $response->getStatusCode());
        } catch (RequestException $e) {
            $this->assertEquals(404, $e->getResponse()->getStatusCode());
        }
    }

    public function testUpdateIssue() {
        // Test case for updating an issue
        $issueKey = "SCRUM-15";
        $fields = [
            'summary' => 'Updated Issue',
        ];

        try {
            $response = $this->client->put("/rest/api/2/issue/$issueKey", [
                'json' => [
                    'fields' => $fields,
                ],
            ]);

            $this->assertEquals(204, $response->getStatusCode());
        } catch (RequestException $e) {
            $this->assertEquals(404, $e->getResponse()->getStatusCode());
        }
    }

    public function testDeleteIssue() {
        // Test case for deleting an issue
        $issueKey = "SCRUM-15";

        try {
            $response = $this->client->delete("/rest/api/2/issue/$issueKey");

            $this->assertEquals(204, $response->getStatusCode());
        } catch (RequestException $e) {
            $this->assertEquals(404, $e->getResponse()->getStatusCode());
        }
    }
}