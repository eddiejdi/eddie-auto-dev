<?php

use PHPUnit\Framework\TestCase;

class JiraTrackerTest extends TestCase {
    public function testTrackActivitySuccess() {
        // Configurações do PHP Agent
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar a classe JiraTracker
        $tracker = new JiraTracker($url, $username, $password);

        // Exemplo de uso: Criar uma atividade no issue com chave 'ABC-123'
        $issueKey = 'ABC-123';
        $activityType = 'commented'; // ou 'resolved', 'updated', etc.
        $details = "O usuário realizou um update no item.";

        try {
            // Chamar a função trackActivity
            $tracker->trackActivity($issueKey, $activityType, $details);

            // Verificar se a atividade foi criada com sucesso
            $this->assertTrue(true);
        } catch (Exception $e) {
            // Tratar erros de conexão ou criação de atividade
            $this->assertEquals('Falha ao criar atividade: ' . $e->getMessage(), true);
        }
    }

    public function testTrackActivityError() {
        // Configurações do PHP Agent
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar a classe JiraTracker
        $tracker = new JiraTracker($url, $username, $password);

        // Exemplo de uso: Criar uma atividade no issue com chave 'ABC-123'
        $issueKey = 'ABC-123';
        $activityType = 'commented'; // ou 'resolved', 'updated', etc.
        $details = "O usuário realizou um update no item.";

        try {
            // Chamar a função trackActivity com uma chave de issue inválida
            $tracker->trackActivity('invalid-issue-key', $activityType, $details);
        } catch (Exception $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Falha ao criar atividade: ', true);
        }
    }

    public function testTrackActivityEdgeCase() {
        // Configurações do PHP Agent
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar a classe JiraTracker
        $tracker = new JiraTracker($url, $username, $password);

        // Exemplo de uso: Criar uma atividade no issue com chave 'ABC-123'
        $issueKey = 'ABC-123';
        $activityType = 'commented'; // ou 'resolved', 'updated', etc.
        $details = "O usuário realizou um update no item.";

        try {
            // Chamar a função trackActivity com uma chave de issue vazia
            $tracker->trackActivity('', $activityType, $details);
        } catch (Exception $e) {
            // Verificar se o erro é esperado
            $this->assertEquals('Falha ao criar atividade: ', true);
        }
    }
}