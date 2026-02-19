<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function testSendDataWithValidData() {
        $data = [
            'task_id' => '12345',
            'status' => 'in progress'
        ];

        $phpAgent = new PhpAgent('localhost', 8080);
        $this->assertEquals("Sending data to PHP Agent: " . json_encode($data) . "\n", $phpAgent->sendData($data));
    }

    public function testSendDataWithInvalidData() {
        $invalidData = [
            'task_id' => null,
            'status' => ''
        ];

        $phpAgent = new PhpAgent('localhost', 8080);
        $this->expectException(\InvalidArgumentException::class, "Task ID cannot be null");
        $phpAgent->sendData($invalidData);
    }
}