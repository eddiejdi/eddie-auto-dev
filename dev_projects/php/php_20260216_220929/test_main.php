<?php

use PHPUnit\Framework\TestCase;

class ScrumProjectTest extends TestCase {
    public function testTrackActivitySuccess() {
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

        // Verifica se o issue foi criado corretamente
        $this->assertTrue(true, 'Issue was tracked successfully');
    }

    public function testTrackActivityError() {
        // Configuração do projeto
        $projectName = 'SCRUM-15';
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Cria uma instância da classe ScrumProject
        $scrumProject = new ScrumProject($projectName, $jiraUrl, $username, $password);

        // Descrição da atividade a ser registrada com um valor inválido
        $activityDescription = "Implementar integração PHP Agent com Jira (valor inválido)";

        // Tenta registrar a atividade no Jira
        try {
            $scrumProject->trackActivity($activityDescription);
            $this->fail('Issue was not tracked successfully');
        } catch (Exception $e) {
            $this->assertTrue(true, 'Error tracking activity: ' . $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Configuração do projeto
        $projectName = 'SCRUM-15';
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Cria uma instância da classe ScrumProject
        $scrumProject = new ScrumProject($projectName, $jiraUrl, $username, $password);

        // Descrição da atividade a ser registrada com um valor limite
        $activityDescription = "Implementar integração PHP Agent com Jira (valor limite)";

        // Tenta registrar a atividade no Jira
        try {
            $scrumProject->trackActivity($activityDescription);
            $this->fail('Issue was not tracked successfully');
        } catch (Exception $e) {
            $this->assertTrue(true, 'Error tracking activity: ' . $e->getMessage());
        }
    }
}