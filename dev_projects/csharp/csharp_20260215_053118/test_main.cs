using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Xunit;

public class TaskTest
{
    [Fact]
    public void Task_Id_ShouldBeSet()
    {
        var task = new Task { Id = 1 };
        Assert.Equal(1, task.Id);
    }

    [Fact]
    public void Task_Title_ShouldBeSet()
    {
        var task = new Task { Title = "Test Task" };
        Assert.Equal("Test Task", task.Title);
    }

    [Fact]
    public void Task_Description_ShouldBeSet()
    {
        var task = new Task { Description = "This is a test description." };
        Assert.Equal("This is a test description.", task.Description);
    }

    [Fact]
    public void Task_CreatedAt_ShouldBeSet()
    {
        var task = new Task { CreatedAt = DateTime.Now };
        Assert.NotNull(task.CreatedAt);
    }
}

public class CSharpAgentTest
{
    [Fact]
    public void AddTask_ShouldAddTaskToList()
    {
        var agent = new CSharpAgent();
        var task = new Task { Id = 1, Title = "Test Task", Description = "This is a test description.", CreatedAt = DateTime.Now };
        agent.AddTask(task);

        Assert.Contains(task, agent.GetAllTasks());
    }

    [Fact]
    public void GetAllTasks_ShouldReturnAllTasks()
    {
        var agent = new CSharpAgent();
        var task1 = new Task { Id = 1, Title = "Test Task 1", Description = "This is a test description.", CreatedAt = DateTime.Now };
        var task2 = new Task { Id = 2, Title = "Test Task 2", Description = "This is a test description.", CreatedAt = DateTime.Now };
        agent.AddTask(task1);
        agent.AddTask(task2);

        var allTasks = agent.GetAllTasks();
        Assert.Contains(task1, allTasks);
        Assert.Contains(task2, allTasks);
    }
}

public class JiraClientTest
{
    [Fact]
    public async Task MonitorEvents_ShouldLogAllTasks()
    {
        var agent = new CSharpAgent();
        var task1 = new Task { Id = 1, Title = "Task 1", Description = "This is a test description.", CreatedAt = DateTime.Now };
        var task2 = new Task { Id = 2, Title = "Test Task 2", Description = "This is a test description.", CreatedAt = DateTime.Now };
        agent.AddTask(task1);
        agent.AddTask(task2);

        var jiraClient = new JiraClient(agent);
        await jiraClient.MonitorEvents();

        // Check if the logs contain all tasks
        // This part of the test would require actual logging or database interaction to verify
    }
}