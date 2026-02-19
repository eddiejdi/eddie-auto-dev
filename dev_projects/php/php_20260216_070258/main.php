<?php

// Importar as classes necessárias
require_once 'JiraClient.php';
require_once 'PHPAgent.php';

class Scrum15 {
    private $jiraClient;
    private $phpAgent;

    public function __construct($jiraUrl, $username, $password) {
        // Inicializar o cliente Jira
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);

        // Inicializar o PHP Agent
        $this->phpAgent = new PHPAgent();
    }

    public function trackActivity($activityName) {
        try {
            // Adicionar a atividade ao PHP Agent
            $this->phpAgent->addActivity($activityName);

            // Salvar a atividade no Jira
            $issueId = $this->jiraClient->createIssue('Task', ['summary' => 'New Task']);
            $this->jiraClient->updateIssue($issueId, ['fields' => ['description' => $this->phpAgent->getActivityLog()]]);

            echo "Atividade '$activityName' registrada no Jira.";
        } catch (Exception $e) {
            echo "Erro ao registrar atividade: " . $e->getMessage();
        }
    }

    public static function main($argv) {
        if ($argc !== 2) {
            echo "Uso: php scrum15.php <atividade>";
            return;
        }

        $activityName = $argv[1];
        $scrum15 = new Scrum15('https://your-jira-url.com', 'your-username', 'your-password');
        $scrum15->trackActivity($activityName);
    }
}

if (__name__ == "__main__") {
    Scrum15::main($_SERVER['argv']);
}