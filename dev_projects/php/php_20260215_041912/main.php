<?php

// Importar classes necessárias
use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraTracker {
    private $agent;

    public function __construct($jiraUrl) {
        try {
            // Configurar o PHP Agent com a URL do Jira
            $this->agent = new Agent([
                'url' => $jiraUrl,
                'username' => 'your_username',
                'password' => 'your_password'
            ]);
        } catch (AgentException $e) {
            echo "Error: " . $e->getMessage();
            exit;
        }
    }

    public function trackActivity($issueKey, $activityType, $description) {
        try {
            // Criar um novo registro de atividade no Jira
            $this->agent->createIssue([
                'key' => $issueKey,
                'fields' => [
                    'summary' => "New Activity",
                    'description' => $description,
                    'issuetype' => ['name' => $activityType],
                    'priority' => ['name' => 'Normal'],
                    'assignee' => ['id' => 'your_assignee_id']
                ]
            ]);
        } catch (AgentException $e) {
            echo "Error: " . $e->getMessage();
        }
    }

    public function runCLI() {
        // Exemplo de uso do CLI
        if ($_SERVER['argc'] > 1) {
            $issueKey = $_SERVER['argv'][1];
            $activityType = $_SERVER['argv'][2];
            $description = implode(' ', array_slice($_SERVER['argv'], 3));

            $this->trackActivity($issueKey, $activityType, $description);
        } else {
            echo "Usage: php jira-tracker.php <issue_key> <activity_type> <description>";
        }
    }

    public function __destruct() {
        // Fechar o PHP Agent
        $this->agent->close();
    }
}

// Executar o script como um programa CLI
if (php_sapi_name() === 'cli') {
    $jiraTracker = new JiraTracker('https://your_jira_url');
    $jiraTracker->runCLI();
}