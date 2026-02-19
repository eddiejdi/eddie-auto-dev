<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {
    private $scrum15;

    protected function setUp(): void {
        $this->scrum15 = new Scrum15('http://jira.example.com', 'admin', 'password', 'SCRUM-15');
    }

    public function testMonitorarProcessos() {
        // Caso de sucesso com valores válidos
        $issueList = $this->scrum15->monitorarProcessos();
        $this->assertNotEmpty($issueList);

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->monitorarProcessos([]);
        } catch (\Exception $e) {
            $this->assertEquals('Divide by zero', $e->getMessage());
        }
    }

    public function testGerenciarRelatorios() {
        // Caso de sucesso
        $this->scrum15->gerenciarRelatorios();
        $this->assertStringContainsString('Gerenciando relatórios...', $this->scrum15->output);

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->gerenciarRelatorios([]);
        } catch (\Exception $e) {
            $this->assertEquals('Divide by zero', $e->getMessage());
        }
    }

    public function testMain() {
        // Caso de sucesso
        $output = Scrum15::main(['http://jira.example.com', 'admin', 'password', 'SCRUM-15']);
        $this->assertStringContainsString('Scrum-15', $output);

        // Caso de erro (divisão por zero)
        try {
            Scrum15::main(['http://jira.example.com', 'admin', 'password', 'SCRUM-15']);
        } catch (\Exception $e) {
            $this->assertEquals('Divide by zero', $e->getMessage());
        }
    }
}