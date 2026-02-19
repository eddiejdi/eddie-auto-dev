<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {
    private $scrum15;

    protected function setUp(): void {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';
        $issueId = 'YOUR-ISSUE-ID';

        // Criar uma instância da classe Scrum15
        $this->scrum15 = new Scrum15($jiraUrl, $username, $password, $issueId);
    }

    public function testRegisterActivity() {
        // Caso de sucesso com valores válidos
        $activity = 'Tarefa iniciada';
        $this->scrum15->registerActivity($activity);

        // Verificar se a atividade foi registrada na log
        $this->assertContains($activity, $this->scrum15->activityLog);
    }

    public function testRegisterActivityError() {
        // Caso de erro (divisão por zero)
        $this->expectException(\Exception::class);

        // Tentar registrar uma atividade com um valor inválido
        $this->scrum15->registerActivity(0); // Divisão por zero
    }

    public function testMonitorActivities() {
        // Caso de sucesso com valores válidos
        $activity = 'Processamento de dados';
        $this->scrum15->registerActivity($activity);

        // Monitorar as atividades da tarefa
        $this->scrum15->monitorActivities();

        // Verificar se a atividade foi registrada na log do Jira
        $issue = new Issue($this->scrum15->jiraClient, $this->issueId);
        $this->assertEquals($activity, $issue->fields['description']);
    }
}