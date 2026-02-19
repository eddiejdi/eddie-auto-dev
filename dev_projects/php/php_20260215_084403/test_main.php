<?php

use PHPUnit\Framework\TestCase;

class MonitoringSystemTest extends TestCase {
    public function testRegisterEvent() {
        // Configuração do sistema de monitoramento
        $jiraClient = new JiraClient();
        $monitoringSystem = new MonitoringSystem($jiraClient);

        // Criar um usuário
        $user = new User(1, 'john_doe', 'john.doe@example.com');

        // Criar um projeto
        $project = new Project(1, 'My Project');

        // Criar um item do projeto
        $item = new ProjectItem(1, 'Task 1', 'Implement feature A');

        // Adicionar o item ao projeto
        $project->addItem($item);

        // Criar uma atividade
        $activity = new Activity(1, $user->getId(), $project->getId(), $item);

        // Registrar a atividade no sistema de monitoramento
        $scrumSystem = new ScrumSystem($monitoringSystem);
        $result = $scrumSystem->trackActivity($activity);

        // Verificar se o resultado é "Created issue in Jira"
        $this->assertEquals("Created issue in Jira", $result);
    }

    public function testRegisterEventError() {
        // Configuração do sistema de monitoramento
        $jiraClient = new JiraClient();
        $monitoringSystem = new MonitoringSystem($jiraClient);

        // Criar um usuário
        $user = new User(1, 'john_doe', 'john.doe@example.com');

        // Criar um projeto
        $project = new Project(1, 'My Project');

        // Criar um item do projeto
        $item = new ProjectItem(1, 'Task 1', 'Implement feature A');

        // Adicionar o item ao projeto
        $project->addItem($item);

        // Criar uma atividade com valores inválidos
        $activity = new Activity(1, null, null, null);

        // Registrar a atividade no sistema de monitoramento
        $scrumSystem = new ScrumSystem($monitoringSystem);
        $result = $scrumSystem->trackActivity($activity);

        // Verificar se o resultado é "Invalid input"
        $this->assertEquals("Invalid input", $result);
    }
}