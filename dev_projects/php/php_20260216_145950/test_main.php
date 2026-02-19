<?php

require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15Test extends \PHPUnit\Framework\TestCase {

    private $jiraClient;
    private $issue;

    public function setUp() {
        // Configuração do Jira
        $this->url = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Criar uma instância da classe Scrum15
        $this->scrum15 = new Scrum15($this->url, $this->username, $this->password);

        // Exemplo de atividade a ser trackeada
        $activityName = "Implement PHP Agent with Jira";

        // Adicionar o issue ao Jira
        try {
            $this->issue->setSummary("Tracking: " . $activityName);
            $this->issue->setDescription("This is a tracking issue for " . $activityName);

            // Adicionar o issue ao Jira
            $this->jiraClient->createIssue($this->issue);

            echo "Activity tracked successfully.\n";
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public function testTrackActivitySuccess() {
        // Caso de sucesso com valores válidos
        $this->scrum15->trackActivity("Implement PHP Agent with Jira");
        $this->assertEquals("Tracking: Implement PHP Agent with Jira", $this->issue->getSummary());
    }

    public function testTrackActivityErrorDivideByZero() {
        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->trackActivity("Implement PHP Agent with Jira");
        } catch (Exception $e) {
            $this->assertEquals("Error tracking activity: Division by zero", $e->getMessage());
        }
    }

    public function testTrackActivityErrorInvalidValue() {
        // Caso de erro (valor inválido)
        try {
            $this->scrum15->trackActivity("Implement PHP Agent with Jira");
        } catch (Exception $e) {
            $this->assertEquals("Error tracking activity: Invalid value", $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCaseNull() {
        // Caso de edge case (valores limite, strings vazias, None)
        try {
            $this->scrum15->trackActivity(null);
        } catch (Exception $e) {
            $this->assertEquals("Error tracking activity: Invalid value", $e->getMessage());
        }
    }

    public function tearDown() {
        // Limpar o issue criado
        if ($this->issue !== null) {
            try {
                $this->jiraClient->deleteIssue($this->issue);
                echo "Activity deleted successfully.\n";
            } catch (Exception $e) {
                echo "Error deleting activity: " . $e->getMessage() . "\n";
            }
        }
    }
}