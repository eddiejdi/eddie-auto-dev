<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use Jira\Client as JiraClient;
use Jira\Issue\Issue;
use Jira\Project\Project;

class Scrum15 {
    private $jiraClient;
    private $issueId;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient([
            'base_url' => $url,
            'auth_type' => 'basic',
            'username' => $username,
            'password' => $password
        ]);
    }

    public function createIssue($summary, $description) {
        $project = Project::getById($this->jiraClient, 'YOUR_PROJECT_ID');
        $issue = Issue::create([
            'project' => $project,
            'summary' => $summary,
            'description' => $description
        ]);

        $this->issueId = $issue['id'];
    }

    public function updateIssue($status) {
        $issue = Issue::getById($this->jiraClient, $this->issueId);
        $issue['fields']['status'] = [
            'name' => $status
        ];

        Issue::update($this->jiraClient, $issue);
    }

    public function main() {
        // Criar uma nova tarefa
        $this->createIssue('Implement Scrum 15', 'Implement the SCRUM 15 project');

        // Atualizar a tarefa para o status em andamento
        $this->updateIssue('In Progress');
    }
}

// Executar o programa
if (__name__ == "__main__") {
    $scrum15 = new Scrum15('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');
    $scrum15->main();
}