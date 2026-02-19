<?php

// Importar classes necessárias
require_once 'vendor/autoload.php';

use PhpAgent\Jira;

class Scrum15 {
    private $jira;
    private $projectKey;

    public function __construct($jiraUrl, $username, $password) {
        $this->jira = new Jira($jiraUrl);
        $this->jira->login($username, $password);
        $this->projectKey = 'YOUR_PROJECT_KEY';
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            $issue = $this->jira->getIssue($this->projectKey, $issueKey);
            $comment = [
                'body' => $activityDescription,
                'visibility' => ['type' => 'private']
            ];
            $this->jira->addComment($issue, $comment);
            echo "Activity tracked successfully for issue {$issueKey}.\n";
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'YOUR_USERNAME';
        $password = 'YOUR_PASSWORD';

        $scrum15 = new Scrum15($jiraUrl, $username, $password);

        // Exemplo de uso
        $issueKey = 'ABC-123';
        $activityDescription = 'User logged in successfully.';
        $scrum15->trackActivity($issueKey, $activityDescription);
    }
}

// Iniciar o script se for CLI
if (php_sapi_name() === 'cli') {
    Scrum15::main();
}