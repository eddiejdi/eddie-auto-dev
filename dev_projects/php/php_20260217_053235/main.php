<?php

// Importar classes necessárias
require_once 'Jira.php';
require_once 'PhpAgent.php';

class ScrumProjectTracker {
    private $jira;
    private $phpAgent;

    public function __construct($jiraUrl, $username, $password) {
        $this->jira = new Jira($jiraUrl, $username, $password);
        $this->phpAgent = new PhpAgent();
    }

    public function trackActivity($issueId, $activityDescription) {
        try {
            // Adicionar atividade ao issue no Jira
            $this->jira->addIssueComment($issueId, $activityDescription);

            // Registrar a atividade no PHP Agent
            $this->phpAgent->logActivity($issueId, $activityDescription);
        } catch (Exception $e) {
            echo "Erro: " . $e->getMessage();
        }
    }

    public static function main() {
        $scrumProjectTracker = new ScrumProjectTracker('https://your-jira-instance.com', 'username', 'password');

        // Exemplo de uso
        $issueId = '12345';
        $activityDescription = 'Implementado o novo sistema.';
        $scrumProjectTracker->trackActivity($issueId, $activityDescription);
    }
}

// Executar o script em modo CLI
if (__name__ == "__main__") {
    ScrumProjectTracker::main();
}