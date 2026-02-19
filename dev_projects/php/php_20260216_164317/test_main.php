<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function testAddTask() {
        $agent = new PhpAgent();
        $task = new Task(1, 'Atualizar banco de dados');

        $this->assertTrue($agent->addTask($task));
    }

    public function testGetTasks() {
        $agent = new PhpAgent();
        $task = new Task(1, 'Atualizar banco de dados');
        $agent->addTask($task);

        $tasks = $agent->getTasks();

        $this->assertEquals(1, count($tasks));
        $this->assertTrue(in_array($task, $tasks));
    }

    public function testMonitor() {
        $agent = new PhpAgent();
        $task = new TaskInJira(1, 'Atualizar banco de dados', 12345);

        $this->assertTrue($agent->addTask($task));

        $monitor = new ActivityMonitor($agent);
        $monitor->monitor();

        // Verifique se as atividades foram exibidas corretamente
    }

    public function testAnalyze() {
        $agent = new PhpAgent();
        $task = new TaskInJira(1, 'Atualizar banco de dados', 12345);

        $this->assertTrue($agent->addTask($task));

        $analyzer = new DataAnalyzer($agent);
        $analyzer->analyze();

        // Verifique se a análise foi realizada corretamente
    }
}