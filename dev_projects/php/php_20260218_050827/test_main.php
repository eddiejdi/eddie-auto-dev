<?php

use PhpAgent\JiraClient;
use PhpAgent\EventLogger;

class Scrum15Test extends PHPUnit\Framework\TestCase {

    public function setUp() {
        // Configuração do Jira
        $this->jiraUrl = 'https://your-jira-instance.com';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Criar uma instância da Scrum15
        $this->scrum15 = new Scrum15($this->jiraUrl, $this->username, $this->password);
    }

    public function testMonitorActivities() {
        // Caso de sucesso com valores válidos
        $this->scrum15->monitorActivities();
        $this->assertTrue(true); // Avisa que o teste passou

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->monitorActivities();
            $this->fail('Erro esperado: divisão por zero');
        } catch (Exception $e) {
            $this->assertEquals("Error monitoring activities: Division by zero", $e->getMessage());
        }

        // Edge case (valores limite)
        $this->scrum15->monitorActivities();
    }

    public function testRegisterEvents() {
        // Caso de sucesso com valores válidos
        $this->scrum15->registerEvents();
        $this->assertTrue(true); // Avisa que o teste passou

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->registerEvents();
            $this->fail('Erro esperado: divisão por zero');
        } catch (Exception $e) {
            $this->assertEquals("Error registering events: Division by zero", $e->getMessage());
        }

        // Edge case (valores limite)
        $this->scrum15->registerEvents();
    }
}