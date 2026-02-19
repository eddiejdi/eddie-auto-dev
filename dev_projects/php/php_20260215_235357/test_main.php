<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    public function testCreateIssue() {
        // Mock the Jira client and issue creation
        $client = $this->createMock(Client::class);
        $issue = new Issue('My New Issue', 'This is a test issue.', '10100');
        
        // Define custom fields for the issue
        $issue->addCustomField('customfield_12345', 'Value 1');
        $issue->addCustomField('customfield_67890', 'Value 2');
        
        // Create a mock response for creating an issue
        $response = new stdClass();
        $response->key = 'ABC-123';
        
        $client->method('POST', '/rest/api/2/issue')->willReturn($response);
        
        // Call the createIssue method of the Jira client
        $createdIssue = $client->createIssue($issue);
        
        // Assert that the issue was created successfully
        $this->assertEquals('ABC-123', $createdIssue->getKey());
    }
    
    public function testCreateIssueError() {
        // Mock the Jira client and issue creation
        $client = $this->createMock(Client::class);
        
        // Define a mock response for creating an issue with an error
        $response = new stdClass();
        $response->error = 'Invalid issue data';
        
        $client->method('POST', '/rest/api/2/issue')->willReturn($response);
        
        // Call the createIssue method of the Jira client
        try {
            $createdIssue = $client->createIssue(new Issue('My New Issue', 'This is a test issue.', '10100'));
            $this->fail('Expected an exception to be thrown');
        } catch (Exception $e) {
            // Assert that the exception was thrown with the correct message
            $this->assertEquals('Invalid issue data', $e->getMessage());
        }
    }
    
    public function testGetIssues() {
        // Mock the Jira client and issue retrieval
        $client = $this->createMock(Client::class);
        
        // Define a mock response for retrieving issues
        $response = new stdClass();
        $response->issues = [
            (object)['id' => 'ABC-123', 'summary' => 'Issue 1'],
            (object)['id' => 'DEF-456', 'summary' => 'Issue 2']
        ];
        
        $client->method('GET', '/rest/api/2/search')->willReturn($response);
        
        // Call the getIssues method of the Jira client
        $issues = $client->getIssues();
        
        // Assert that the issues were retrieved successfully
        $this->assertEquals(2, count($issues));
    }
}