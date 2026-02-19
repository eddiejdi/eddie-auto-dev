<?php

use PHPUnit\Framework\TestCase;

class ActivityTrackerTest extends TestCase {
    public function testAddTask() {
        $activityTracker = new ActivityTracker();
        $task = new Task(1, 'Task 1', 'Description of task 1');
        $this->assertTrue($activityTracker->addTask($task));
    }

    public function testAddUser() {
        $activityTracker = new ActivityTracker();
        $user = new User(1, 'John Doe');
        $this->assertTrue($activityTracker->addUser($user));
    }

    public function testAddActivity() {
        $activityTracker = new ActivityTracker();
        $task = new Task(1, 'Task 1', 'Description of task 1');
        $user = new User(1, 'John Doe');
        $activity = new Activity(1, 1, 1, 'Completed');
        $this->assertTrue($activityTracker->addActivity($activity));
    }

    public function testListTasks() {
        $activityTracker = new ActivityTracker();
        $task1 = new Task(1, 'Task 1', 'Description of task 1');
        $task2 = new Task(2, 'Task 2', 'Description of task 2');
        $this->assertTrue($activityTracker->addTask($task1));
        $this->assertTrue($activityTracker->addTask($task2));
        $this->assertEquals([$task1, $task2], $activityTracker->listTasks());
    }

    public function testListUsers() {
        $activityTracker = new ActivityTracker();
        $user1 = new User(1, 'John Doe');
        $user2 = new User(2, 'Jane Doe');
        $this->assertTrue($activityTracker->addUser($user1));
        $this->assertTrue($activityTracker->addUser($user2));
        $this->assertEquals([$user1, $user2], $activityTracker->listUsers());
    }

    public function testListActivities() {
        $activityTracker = new ActivityTracker();
        $task = new Task(1, 'Task 1', 'Description of task 1');
        $user = new User(1, 'John Doe');
        $activity = new Activity(1, 1, 1, 'Completed');
        $this->assertTrue($activityTracker->addTask($task));
        $this->assertTrue($activityTracker->addUser($user));
        $this->assertTrue($activityTracker->addActivity($activity));
        $this->assertEquals([$activity], $activityTracker->listActivities());
    }
}