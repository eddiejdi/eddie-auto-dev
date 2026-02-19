<?php

use PHPUnit\Framework\TestCase;

class ActivityTest extends TestCase {
    public function testCreateActivity() {
        $activity = new Activity(1, 'Implement PHP Agent with Jira', 'In Progress');
        $this->assertEquals(1, $activity->getId());
        $this->assertEquals('Implement PHP Agent with Jira', $activity->getSummary());
        $this->assertEquals('In Progress', $activity->getStatus());
    }

    public function testSetActivityProperties() {
        $activity = new Activity(1, 'Implement PHP Agent with Jira', 'In Progress');
        $activity->setId(2);
        $activity->setSummary('Update PHP Agent with Jira');
        $activity->setStatus('Completed');

        $this->assertEquals(2, $activity->getId());
        $this->assertEquals('Update PHP Agent with Jira', $activity->getSummary());
        $this->assertEquals('Completed', $activity->getStatus());
    }
}

class PhpAgentTest extends TestCase {
    public function testSendToJira() {
        $activity = new Activity(1, 'Implement PHP Agent with Jira', 'In Progress');
        $phpAgent = new PhpAgent($activity);

        // Simulação da envio à API do Jira (pode ser substituída por uma chamada real)
        $this->assertEquals("Sending activity to Jira: Implement PHP Agent with Jira - In Progress\n", $phpAgent->sendToJira());
    }

    public function testSendToJiraWithInvalidActivity() {
        $activity = new Activity(null, '', '');
        $phpAgent = new PhpAgent($activity);

        // Simulação da envio à API do Jira (pode ser substituída por uma chamada real)
        $this->assertEquals("Sending activity to Jira: null - \n", $phpAgent->sendToJira());
    }
}