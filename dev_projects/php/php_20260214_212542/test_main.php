<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function setUp() {
        $this->monitor = new ActivityMonitor();
    }

    public function testTrackActivityWithValidData() {
        $event = 'User logged in';
        $this->monitor->trackActivity($event);
        $events = $this->monitor->getEvents();
        $this->assertEquals(1, count($events));
        $this->assertEquals('activity', $events[0]->type);
        $this->assertEquals($event, $events[0]->data);
    }

    public function testTrackActivityWithInvalidData() {
        $event = null;
        $this->monitor->trackActivity($event);
        $events = $this->monitor->getEvents();
        $this->assertEquals(0, count($events));
    }
}