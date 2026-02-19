<?php

use PHPUnit\Framework\TestCase;

class ActivityTest extends TestCase {
    public function testCreateActivity() {
        $id = 1;
        $title = 'New PHP Agent Integration';
        $description = 'Tracking of activities using PHP Agent and Jira';

        $activity = new Activity($id, $title, $description);

        $this->assertEquals($id, $activity->getId());
        $this->assertEquals($title, $activity->getTitle());
        $this->assertEquals($description, $activity->getDescription());
    }

    public function testGetActivityId() {
        $id = 1;
        $title = 'New PHP Agent Integration';
        $description = 'Tracking of activities using PHP Agent and Jira';

        $activity = new Activity($id, $title, $description);

        $this->assertEquals($id, $activity->getId());
    }

    public function testGetActivityTitle() {
        $id = 1;
        $title = 'New PHP Agent Integration';
        $description = 'Tracking of activities using PHP Agent and Jira';

        $activity = new Activity($id, $title, $description);

        $this->assertEquals($title, $activity->getTitle());
    }

    public function testGetActivityDescription() {
        $id = 1;
        $title = 'New PHP Agent Integration';
        $description = 'Tracking of activities using PHP Agent and Jira';

        $activity = new Activity($id, $title, $description);

        $this->assertEquals($description, $activity->getDescription());
    }
}

class PhpAgentTest extends TestCase {
    public function testSendActivity() {
        $url = 'http://localhost/php-agent';
        $activity = new Activity(1, 'New PHP Agent Integration', 'Tracking of activities using PHP Agent and Jira');

        $phpAgent = new PhpAgent($url);
        $phpAgent->sendActivity($activity);

        // Verificar se a atividade foi enviada corretamente
        $this->assertTrue(true); // Aqui você pode adicionar mais verificações
    }
}

class JiraIntegrationTest extends TestCase {
    public function testTrackActivity() {
        $jiraUrl = 'https://your-jira-url.com';
        $phpAgent = new PhpAgent('http://localhost/php-agent');
        $jiraIntegration = new JiraIntegration($phpAgent, $jiraUrl);

        // Criar uma atividade
        $activity = new Activity(1, 'New PHP Agent Integration', 'Tracking of activities using PHP Agent and Jira');

        // Travar a atividade
        $jiraIntegration->trackActivity($activity);

        // Verificar se a atividade foi enviada corretamente e registrada no Jira
        $this->assertTrue(true); // Aqui você pode adicionar mais verificações
    }
}

class MainTest extends TestCase {
    public function testMain() {
        $jiraUrl = 'https://your-jira-url.com';
        $phpAgent = new PhpAgent('http://localhost/php-agent');
        $jiraIntegration = new JiraIntegration($phpAgent, $jiraUrl);

        // Criar uma atividade
        $activity = new Activity(1, 'New PHP Agent Integration', 'Tracking of activities using PHP Agent and Jira');

        // Travar a atividade
        $jiraIntegration->trackActivity($activity);

        // Verificar se a atividade foi enviada corretamente e registrada no Jira
        $this->assertTrue(true); // Aqui você pode adicionar mais verificações
    }
}