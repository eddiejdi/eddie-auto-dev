<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    protected $agent;

    public function setUp(): void {
        // Configuração do PHP Agent
        $this->agent = new Agent('your-jira-project-key', 'your-php-agent-token');
    }

    public function testAuthenticate() {
        try {
            $this->assertTrue($this->agent->authenticate());
        } catch (\Exception $e) {
            $this->fail("Erro ao autenticar: " . $e->getMessage());
        }
    }

    public function testCreateActivity() {
        try {
            $activity = ['title' => 'Início do projeto', 'status' => 'Open'];
            $this->assertTrue($this->agent->createActivity($activity['title'], $activity['status']));
        } catch (\Exception $e) {
            $this->fail("Erro ao criar atividade: " . $e->getMessage());
        }
    }

    public function testUpdateActivityStatus() {
        try {
            $activity = ['title' => 'Início do projeto', 'status' => 'Open'];
            $this->assertTrue($this->agent->createActivity($activity['title'], $activity['status']));
            $this->assertTrue($this->agent->updateActivityStatus($activity['title'], 'In Progress'));
        } catch (\Exception $e) {
            $this->fail("Erro ao atualizar status da atividade: " . $e->getMessage());
        }
    }

    public function testFinish() {
        try {
            $this->assertTrue($this->agent->finish());
        } catch (\Exception $e) {
            $this->fail("Erro ao finalizar integração com Jira: " . $e->getMessage());
        }
    }

    public function testStartIntegrationWithValidData() {
        try {
            startIntegration();
        } catch (\Exception $e) {
            $this->fail("Erro ao integrar com Jira: " . $e->getMessage());
        }
    }

    public function testStartIntegrationWithError() {
        // Simule um erro durante o processo de integração
        $this->expectException(\Exception::class);
        startIntegration();
    }
}