<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\PhpAgent;
use PhpAgent\Jira\JiraClient;

class JiraIntegration
{
    private $jiraClient;

    public function __construct($jiraUrl, $username, $password)
    {
        // Configurar o cliente Jira
        $this->jiraClient = new JiraClient($jiraUrl);
        $this->jiraClient->login($username, $password);
    }

    public function trackIssue($issueKey, $status)
    {
        try {
            // Atualizar o status do issue
            $this->jiraClient->updateIssueStatus($issueKey, $status);

            echo "Issue {$issueKey} updated to {$status}\n";
        } catch (\Exception $e) {
            echo "Error updating issue: " . $e->getMessage() . "\n";
        }
    }

    public function logEvent($issueKey, $event)
    {
        try {
            // Logar um evento no issue
            $this->jiraClient->logIssueEvent($issueKey, $event);

            echo "Event logged for issue {$issueKey}\n";
        } catch (\Exception $e) {
            echo "Error logging event: " . $e->getMessage() . "\n";
        }
    }

    public function main()
    {
        // Exemplo de uso
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $integration = new JiraIntegration($jiraUrl, $username, $password);

        $issueKey = 'ABC-123';
        $status = 'In Progress';
        $event = 'Task Started';

        $integration->trackIssue($issueKey, $status);
        $integration->logEvent($issueKey, $event);
    }
}

if (__name__ == "__main__") {
    JiraIntegration::main();
}