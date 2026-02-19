<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {

    private $scrum15;

    protected function setUp(): void {
        $this->scrum15 = new Scrum15('https://your-jira-url.com', 'your-jira-token');
    }

    public function testMonitorarAtividades() {
        // Caso de sucesso com valores válidos
        $atualizacao = "Nova atualização do PHP Agent";
        $this->scrum15->phpAgent->setAtualizacao($atualizacao);
        $this->scrum15->monitorarAtividades();
        $this->assertEquals($atualizacao, $this->scrum15->jiraClient->getUltimaAtualizacao());

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->phpAgent->setAtualizacao(0);
            $this->scrum15->monitorarAtividades();
        } catch (\Exception $e) {
            $this->assertEquals("Erro: Divisão por zero", $e->getMessage());
        }
    }

    public function testEmitirRelatorio() {
        // Caso de sucesso com valores válidos
        $relatorio = "Novo relatório de atividades";
        $this->scrum15->phpAgent->setRelatorio($relatorio);
        $this->scrum15->emitirRelatorio();
        $this->assertEquals($relatorio, $this->scrum15->jiraClient->getUltimoRelatorio());

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->phpAgent->setRelatorio(0);
            $this->scrum15->emitirRelatorio();
        } catch (\Exception $e) {
            $this->assertEquals("Erro: Divisão por zero", $e->getMessage());
        }
    }

    public function testMain() {
        // Caso de sucesso com valores válidos
        $this->scrum15->monitorarAtividades();
        $this->scrum15->emitirRelatorio();

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->phpAgent->setAtualizacao(0);
            $this->scrum15->monitorarAtividades();
        } catch (\Exception $e) {
            $this->assertEquals("Erro: Divisão por zero", $e->getMessage());
        }
    }
}