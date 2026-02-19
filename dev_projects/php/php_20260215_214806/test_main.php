<?php

use PHPUnit\Framework\TestCase;

class ActivitySystemTest extends TestCase {
    public function testAddTask() {
        $activitySystem = new ActivitySystem();
        $task = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
        $this->assertTrue($activitySystem->addTask($task));
    }

    public function testUpdateActivity() {
        $activitySystem = new ActivitySystem();
        $task = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
        $activitySystem->addTask($task);
        $updatedTask = new Task(1, 'Implement feature Y', 'Implement the feature Y in the project.');
        $this->assertTrue($activitySystem->updateActivity($updatedTask));
    }

    public function testDeleteActivity() {
        $activitySystem = new ActivitySystem();
        $task = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
        $this->assertTrue($activitySystem->addTask($task));
        $this->assertTrue($activitySystem->deleteActivity($task));
    }

    public function testGetTasksByUser() {
        $activitySystem = new ActivitySystem();
        $user1 = new User(1, 'John Doe');
        $project1 = new Project(1, 'Project A');
        $task1 = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
        $this->assertTrue($activitySystem->addTask($task1));
        $this->assertEquals([$task1], $activitySystem->getTasksByUser($user1));
    }

    public function testGetTasksByProject() {
        $activitySystem = new ActivitySystem();
        $user1 = new User(1, 'John Doe');
        $project1 = new Project(1, 'Project A');
        $task1 = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
        $this->assertTrue($activitySystem->addTask($task1));
        $this->assertEquals([$task1], $activitySystem->getTasksByProject($project1));
    }
}