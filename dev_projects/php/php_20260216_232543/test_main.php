<?php

use PHPUnit\Framework\TestCase;

class ActivityMonitorTest extends TestCase {
    public function testIsActivityCompleted() {
        $activity = new Activity(1, 'Task 1', 'pending');
        $this->assertFalse($this->monitor->isActivityCompleted($activity));
    }

    public function testMonitorActivities() {
        $activities = [
            new Activity(1, 'Task 1', 'pending'),
            new Activity(2, 'Task 2', 'in progress'),
            new Activity(3, 'Task 3', 'completed')
        ];

        $this->monitor->monitorActivities($activities);

        foreach ($activities as $activity) {
            if (!$this->isActivityCompleted($activity)) {
                $this->fail("Failed to update task status for activity {$activity->getId()}");
            }
        }
    }

    public function testGenerateReport() {
        $activities = [
            new Activity(1, 'Task 1', 'pending'),
            new Activity(2, 'Task 2', 'in progress'),
            new Activity(3, 'Task 3', 'completed')
        ];

        $report = $this->monitor->generateReport($activities);

        $this->assertNotEmpty($report->getActivities());
    }

    private function monitor;
}