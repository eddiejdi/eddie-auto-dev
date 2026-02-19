<?php

use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraTrackerTest extends \PHPUnit\Framework\TestCase {

    private $jiraUrl = 'https://your_jira_url';
    private $issueKey = 'ABC-123';
    private $activityType = 'Task';
    private $description = 'Implement new feature';

    public function setUp(): void {
        try {
            // Configurar o PHP Agent com a URL do Jira
            $this->agent = new Agent([
                'url' => $this->jiraUrl,
                'username' => 'your_username',
                'password' => 'your_password'
            ]);
        } catch (AgentException $e) {
            echo "Error: " . $e->getMessage();
            exit;
        }
    }

    public function tearDown(): void {
        // Fechar o PHP Agent
        $this->agent->close();
    }

    public function testTrackActivitySuccess() {
        try {
            // Criar um novo registro de atividade no Jira com valores válidos
            $this->agent->createIssue([
                'key' => $this->issueKey,
                'fields' => [
                    'summary' => "New Activity",
                    'description' => $this->description,
                    'issuetype' => ['name' => $this->activityType],
                    'priority' => ['name' => 'Normal'],
                    'assignee' => ['id' => 'your_assignee_id']
                ]
            ]);
        } catch (AgentException $e) {
            $this->fail("Error: " . $e->getMessage());
        }
    }

    public function testTrackActivityFailureInvalidIssueKey() {
        try {
            // Criar um novo registro de atividade com um issue key inválido
            $this->agent->createIssue([
                'key' => 'INVALID-KEY',
                'fields' => [
                    'summary' => "New Activity",
                    'description' => $this->description,
                    'issuetype' => ['name' => $this->activityType],
                    'priority' => ['name' => 'Normal'],
                    'assignee' => ['id' => 'your_assignee_id']
                ]
            ]);
        } catch (AgentException $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Invalid issue key', $e->getMessage());
        }
    }

    public function testTrackActivityFailureInvalidActivityType() {
        try {
            // Criar um novo registro de atividade com um tipo de atividade inválido
            $this->agent->createIssue([
                'key' => $this->issueKey,
                'fields' => [
                    'summary' => "New Activity",
                    'description' => $this->description,
                    'issuetype' => ['name' => 'InvalidType'],
                    'priority' => ['name' => 'Normal'],
                    'assignee' => ['id' => 'your_assignee_id']
                ]
            ]);
        } catch (AgentException $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Invalid issue type', $e->getMessage());
        }
    }

    public function testTrackActivityFailureInvalidDescription() {
        try {
            // Criar um novo registro de atividade com uma descrição inválida
            $this->agent->createIssue([
                'key' => $this->issueKey,
                'fields' => [
                    'summary' => "New Activity",
                    'description' => '',
                    'issuetype' => ['name' => $this->activityType],
                    'priority' => ['name' => 'Normal'],
                    'assignee' => ['id' => 'your_assignee_id']
                ]
            ]);
        } catch (AgentException $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Invalid description', $e->getMessage());
        }
    }

    public function testRunCLISuccess() {
        try {
            // Executar o script como um programa CLI com valores válidos
            $jiraTracker = new JiraTracker($this->jiraUrl);
            $jiraTracker->runCLI();
        } catch (Exception $e) {
            $this->fail("Error: " . $e->getMessage());
        }
    }

    public function testRunCLIFailureInvalidArguments() {
        try {
            // Executar o script como um programa CLI com argumentos inválidos
            $jiraTracker = new JiraTracker($this->jiraUrl);
            $jiraTracker->runCLI('INVALID-KEY', 'Task');
        } catch (Exception $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Usage: php jira-tracker.php <issue_key> <activity_type> <description>', $e->getMessage());
        }
    }
}