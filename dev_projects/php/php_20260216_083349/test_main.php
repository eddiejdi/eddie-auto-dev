<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function testConnectToJira() {
        $this->expectException(Exception::class);
        connectToJira('https://your-jira-instance.atlassian.net', 'your-jira-username', 'your-jira-password');
    }

    public function testCreateTicket() {
        $client = new \PhpAgent\Client('http://localhost:8080');
        $ticket = createTicket($client, 'Novo Ticket - PHP Agent', 'Este é um exemplo de relatório via email enviado pelo PHP Agent.');
        $this->assertNotEmpty($ticket);
    }

    public function testSendReportViaEmail() {
        $client = new \PhpAgent\Client('http://localhost:8080');
        sendReportViaEmail($client, "Relatório do Ticket {$ticket['key']}\n");
        // Adicionar assertions para verificar se o email foi enviado corretamente
    }
}