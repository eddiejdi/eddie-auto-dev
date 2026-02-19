<?php

// Importar as classes necessárias para integração com PHP Agent e Jira
require_once 'PHPAgent.php';
require_once 'JiraClient.php';

class ScrumProject {
    private $projectName;
    private $jiraClient;

    public function __construct($projectName, $jiraUrl, $username, $password) {
        $this->projectName = $projectName;
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
    }

    public function trackActivity($activityDescription) {
        try {
            // Criação de um novo issue no Jira
            $issueData = [
                'fields' => [
                    'project' => ['key' => $this->projectName],
                    'summary' => $activityDescription,
                    'description' => $activityDescription,
                    'issuetype' => ['name' => 'Task']
                ]
            ];

            $issue = $this->jiraClient->createIssue($issueData);
            echo "Activity tracked successfully: {$issue['key']}\n";
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        // Configuração do projeto
        $projectName = 'SCRUM-15';
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Cria uma instância da classe ScrumProject
        $scrumProject = new ScrumProject($projectName, $jiraUrl, $username, $password);

        // Descrição da atividade a ser registrada
        $activityDescription = "Implementar integração PHP Agent com Jira";

        // Registra a atividade no Jira
        $scrumProject->trackActivity($activityDescription);
    }
}

// Executar o script principal se for CLI
if (php_sapi_name() === 'cli') {
    ScrumProject::main();
}