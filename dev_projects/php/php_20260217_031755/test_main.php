<?php

use Jira\Client;
use Jira\Issue;

class Scrum15Test extends PHPUnit\Framework\TestCase {
    private $jiraClient;

    public function setUp(): void {
        $this->jiraClient = new Client([
            'url' => 'https://your-jira-instance.atlassian.net',
            'auth' => ['your-username', 'your-password']
        ]);
    }

    public function testRegisterEvent() {
        $issueId = 12345; // Exemplo de issue ID válido
        $event = "Issue updated";

        try {
            $this->jiraClient->issues()->get($issueId)->update([
                'fields' => [
                    'customfield_10100' => $event
                ]
            ]);
        } catch (\Exception $e) {
            $this->fail("Failed to register event: " . $e->getMessage());
        }

        // Verificar se o evento foi registrado corretamente
        $updatedIssue = $this->jiraClient->issues()->get($issueId);
        $this->assertEquals($event, $updatedIssue->fields['customfield_10100']);
    }

    public function testRegisterEventError() {
        $issueId = 67890; // Exemplo de issue ID inválido
        $event = "Issue updated";

        try {
            $this->jiraClient->issues()->get($issueId)->update([
                'fields' => [
                    'customfield_10100' => $event
                ]
            ]);
        } catch (\Exception $e) {
            // Verificar se o erro foi capturado corretamente
            $this->assertEquals("Issue not found", $e->getMessage());
        }
    }

    public function testMonitorActivity() {
        $issueId = 12345; // Exemplo de issue ID válido
        $event = "Issue updated";

        try {
            $this->jiraClient->issues()->get($issueId)->update([
                'fields' => [
                    'customfield_10100' => $event
                ]
            ]);
        } catch (\Exception $e) {
            $this->fail("Failed to register event: " . $e->getMessage());
        }

        // Verificar se o evento foi registrado corretamente
        $updatedIssue = $this->jiraClient->issues()->get($issueId);
        $this->assertEquals($event, $updatedIssue->fields['customfield_10100']);
    }
}