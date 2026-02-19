<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraClientTest extends PHPUnit\Framework\TestCase {

    public function testCreateIssue() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        // Criar um novo issue
        $issue = new Issue();
        $issue->setSummary('Teste de Scrum');
        $issue->setDescription('Este é um teste para a integração com Jira usando PHP Agent.');
        $issue->setType('bug');

        // Adicionar tags ao issue
        $issue->addTag('scrum');
        $issue->addTag('test');

        // Criar o issue no Jira
        try {
            $createdIssue = $jira->createIssue($issue);
            $this->assertNotEmpty($createdIssue, 'Issue não criado com sucesso.');
        } catch (Exception $e) {
            $this->fail("Erro ao criar issue: " . $e->getMessage());
        }
    }

    public function testCreateIssueWithInvalidSummary() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        // Criar um novo issue com uma descrição inválida
        $issue = new Issue();
        $issue->setSummary('');
        $issue->setDescription('Este é um teste para a integração com Jira usando PHP Agent.');
        $issue->setType('bug');

        try {
            $jira->createIssue($issue);
            $this->fail("Erro esperado ao criar issue com descrição vazia.");
        } catch (Exception $e) {
            // Verificar se o erro é do tipo InvalidSummaryException
            $this->assertInstanceOf(InvalidSummaryException::class, $e);
        }
    }

    public function testCreateIssueWithInvalidType() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        // Criar um novo issue com um tipo inválido
        $issue = new Issue();
        $issue->setSummary('Teste de Scrum');
        $issue->setDescription('Este é um teste para a integração com Jira usando PHP Agent.');
        $issue->setType('');

        try {
            $jira->createIssue($issue);
            $this->fail("Erro esperado ao criar issue com tipo inválido.");
        } catch (Exception $e) {
            // Verificar se o erro é do tipo InvalidTypeException
            $this->assertInstanceOf(InvalidTypeException::class, $e);
        }
    }

    public function testGetActivity() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        // Monitoramento de atividades (exemplo)
        try {
            $activity = $jira->getActivity('your-username', 'your-password');
            $this->assertNotEmpty($activity, 'Atividade não monitorada.');
        } catch (Exception $e) {
            $this->fail("Erro ao monitorar atividades: " . $e->getMessage());
        }
    }

    public function testGetActivityWithInvalidUsername() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        try {
            $activity = $jira->getActivity('invalid-username', 'your-password');
            $this->fail("Erro esperado ao monitorar atividades com usuário inválido.");
        } catch (Exception $e) {
            // Verificar se o erro é do tipo InvalidUsernameException
            $this->assertInstanceOf(InvalidUsernameException::class, $e);
        }
    }

    public function testGetActivityWithInvalidPassword() {
        // Configuração do Jira
        $jira = new JiraClient('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

        try {
            $activity = $jira->getActivity('your-username', 'invalid-password');
            $this->fail("Erro esperado ao monitorar atividades com senha inválida.");
        } catch (Exception $e) {
            // Verificar se o erro é do tipo InvalidPasswordException
            $this->assertInstanceOf(InvalidPasswordException::class, $e);
        }
    }
}