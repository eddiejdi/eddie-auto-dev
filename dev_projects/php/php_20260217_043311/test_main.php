<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase
{
    public function testCreateIssueWithValidData()
    {
        $title = 'Teste Issue';
        $description = 'Descrição do teste';

        $response = createIssue($title, $description);

        $this->assertArrayHasKey('id', $response);
        $this->assertEquals('Task', $response['fields']['issuetype']['name']);
    }

    public function testCreateIssueWithInvalidData()
    {
        $title = '';
        $description = 'Descrição do teste';

        try {
            createIssue($title, $description);
            $this->fail('Exceção esperada');
        } catch (Exception $e) {
            $this->assertEquals('Jira API error: Invalid issue data', $e->getMessage());
        }
    }

    public function testMonitorActivityWithValidData()
    {
        // Implementação do teste para monitorActivity
    }

    public function testMonitorActivityWithInvalidData()
    {
        // Implementação do teste para monitorActivity
    }
}