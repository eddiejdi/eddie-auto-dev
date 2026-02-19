<?php

use PhpAgent\Agent;
use PhpAgent\Jira;

class JiraTrackerTest extends TestCase {
    protected $tracker;

    public function setUp() {
        // Configurar o PHP Agent
        $this->agent = new Agent();
        $this->agent->setHost('http://localhost:8080');
        $this->agent->setUsername('admin');
        $this->agent->setPassword('password');

        // Configurar o Jira
        $this->jira = new Jira($this->agent);
        $this->tracker = new JiraTracker($this->agent, '12345', 'In Progress');
    }

    public function testTrackTaskWithValidData() {
        $taskId = '12345';
        $status = 'In Progress';

        $this->tracker->trackTask($taskId, $status);

        // Verificar se a tarefa foi atualizada corretamente
        $updatedTask = $this->jira->getTask($taskId);
        $this->assertEquals($status, $updatedTask['fields']['status']['name']);
    }

    public function testTrackTaskWithInvalidData() {
        $taskId = '12345';
        $status = '';

        try {
            $this->tracker->trackTask($taskId, $status);
            $this->fail('Deveria lançar exceção');
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao atualizar tarefa: Status não pode ser vazio', $e->getMessage());
        }
    }

    public function testTrackTaskWithNullData() {
        $taskId = '12345';
        $status = null;

        try {
            $this->tracker->trackTask($taskId, $status);
            $this->fail('Deveria lançar exceção');
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao atualizar tarefa: Status não pode ser vazio', $e->getMessage());
        }
    }

    public function testTrackTaskWithEmptyData() {
        $taskId = '12345';
        $status = '';

        try {
            $this->tracker->trackTask($taskId, $status);
            $this->fail('Deveria lançar exceção');
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao atualizar tarefa: Status não pode ser vazio', $e->getMessage());
        }
    }

    public function testTrackTaskWithInvalidUrl() {
        $url = 'http://localhost:8080';
        $username = 'admin';
        $password = 'password';

        try {
            $this->jira = new Jira($this->agent);
            $this->tracker = new JiraTracker($url, $username, $password);
            $taskId = '12345';
            $status = 'In Progress';

            $this->tracker->trackTask($taskId, $status);
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao conectar com o servidor Jira', $e->getMessage());
        }
    }

    public function testTrackTaskWithInvalidUsername() {
        $url = 'http://localhost:8080';
        $username = '';
        $password = 'password';

        try {
            $this->jira = new Jira($this->agent);
            $this->tracker = new JiraTracker($url, $username, $password);
            $taskId = '12345';
            $status = 'In Progress';

            $this->tracker->trackTask($taskId, $status);
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao conectar com o servidor Jira', $e->getMessage());
        }
    }

    public function testTrackTaskWithInvalidPassword() {
        $url = 'http://localhost:8080';
        $username = 'admin';
        $password = '';

        try {
            $this->jira = new Jira($this->agent);
            $this->tracker = new JiraTracker($url, $username, $password);
            $taskId = '12345';
            $status = 'In Progress';

            $this->tracker->trackTask($taskId, $status);
        } catch (\Exception $e) {
            // Verificar se a exceção foi lançada corretamente
            $this->assertEquals('Erro ao conectar com o servidor Jira', $e->getMessage());
        }
    }
}