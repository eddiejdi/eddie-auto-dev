<?php

use PHPUnit\Framework\TestCase;

class ActivityItemTest extends TestCase {
    public function testDisplay() {
        $activityItem = new ActivityItem(1, "Início do projeto", "Planned");
        ob_start();
        $activityItem->display();
        $output = ob_get_clean();
        $this->assertEquals("ID: 1\nDescrição: Início do projeto\nStatus: Planned\n", $output);
    }

    public function testInvalidId() {
        $this->expectException(\InvalidArgumentException::class);
        new ActivityItem(null, "Início do projeto", "Planned");
    }
}

class ActivityServiceTest extends TestCase {
    public function testAddItem() {
        $activityService = new ActivityService();
        $activityItem1 = new ActivityItem(1, "Início do projeto", "Planned");
        $this->assertTrue($activityService->addItem($activityItem1));
    }

    public function testListItems() {
        $activityService = new ActivityService();
        $activityItem1 = new ActivityItem(1, "Início do projeto", "Planned");
        $activityItem2 = new ActivityItem(2, "Conclusão do projeto", "Completed");
        $this->assertTrue($activityService->addItem($activityItem1));
        $this->assertTrue($activityService->addItem($activityItem2));

        ob_start();
        $activityService->listItems();
        $output = ob_get_clean();
        $expectedOutput = <<<EOT
Item 1:
ID: 1
Descrição: Início do projeto
Status: Planned

Item 2:
ID: 2
Descrição: Conclusão do projeto
Status: Completed

EOT;
        $this->assertEquals($expectedOutput, $output);
    }
}

class PHPAgentTest extends TestCase {
    public function testSendActivity() {
        $activityService = new ActivityService();
        $activityItem1 = new ActivityItem(1, "Início do projeto", "Planned");
        $this->assertTrue($activityService->addItem($activityItem1));

        ob_start();
        $phpAgent = new PHPAgent($activityService);
        $phpAgent->sendActivity($activityItem1);
        $output = ob_get_clean();
        $expectedOutput = <<<EOT
Item 1:
ID: 1
Descrição: Início do projeto
Status: Planned

EOT;
        $this->assertEquals($expectedOutput, $output);
    }
}