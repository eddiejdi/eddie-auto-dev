<?php

// Importar classes necessárias
require_once 'Jira.php';
require_once 'PhpAgent.php';

class PhpAgentTest extends PHPUnit\Framework\TestCase {

    public function testIntegratePhpAgentWithJira() {
        // Caso de sucesso com valores válidos
        $this->assertTrue(integratePhpAgentWithJira('https://your-jira-instance.com', 'your-username', 'your-password'));

        // Caso de erro (divisão por zero)
        try {
            integratePhpAgentWithJira('https://your-jira-instance.com', 'your-username', '');
            $this->fail("Erro esperado: divisão por zero");
        } catch (Exception $e) {
            $this->assertEquals("Divide by zero", $e->getMessage());
        }

        // Caso de erro (valores inválidos)
        try {
            integratePhpAgentWithJira('https://your-jira-instance.com', '', '');
            $this->fail("Erro esperado: valores inválidos");
        } catch (Exception $e) {
            $this->assertEquals("Invalid credentials", $e->getMessage());
        }
    }

    public function testAddActivity() {
        // Caso de sucesso
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';
        $activity = 'Integração PHP Agent com Jira';

        integratePhpAgentWithJira($jiraUrl, $username, $password);

        // Verificar se a atividade foi adicionada ao Jira
        $this->assertTrue(Jira::getInstance()->isActivityAdded($activity));
    }
}