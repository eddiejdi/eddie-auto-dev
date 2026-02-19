using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    private readonly Client _client;

    public ProgramTests()
    {
        _client = new Client("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
    }

    [Fact]
    public async Task CreateProjectTest()
    {
        var project = await _client.Projects.CreateAsync(new ProjectCreateRequest
        {
            Key = "NEWPRJ",
            Name = "New Project"
        });

        Assert.NotNull(project);
        Assert.Equal("NEWPRJ", project.Key);
    }

    [Fact]
    public async Task CreateTaskTest()
    {
        var project = await _client.Projects.CreateAsync(new ProjectCreateRequest
        {
            Key = "NEWPRJ",
            Name = "New Project"
        });

        var task = await _client.Tasks.CreateAsync(project.Id, new TaskCreateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities."
        });

        Assert.NotNull(task);
        Assert.Equal("NEWPRJ-1", task.Key);
    }

    [Fact]
    public async Task UpdateTaskTest()
    {
        var project = await _client.Projects.CreateAsync(new ProjectCreateRequest
        {
            Key = "NEWPRJ",
            Name = "New Project"
        });

        var task = await _client.Tasks.CreateAsync(project.Id, new TaskCreateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities."
        });

        await _client.Tasks.UpdateAsync(task.Id, new TaskUpdateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities.",
            Status = TaskStatus.InProgress,
            Assignee = new User { Key = "assignee-key" }
        });

        var updatedTask = await _client.Tasks.GetAsync(task.Id);

        Assert.NotNull(updatedTask);
        Assert.Equal("NEWPRJ-1", updatedTask.Key);
        Assert.Equal(TaskStatus.InProgress, updatedTask.Status);
    }

    [Fact]
    public async Task CompleteTaskTest()
    {
        var project = await _client.Projects.CreateAsync(new ProjectCreateRequest
        {
            Key = "NEWPRJ",
            Name = "New Project"
        });

        var task = await _client.Tasks.CreateAsync(project.Id, new TaskCreateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities."
        });

        await _client.Tasks.UpdateAsync(task.Id, new TaskUpdateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities.",
            Status = TaskStatus.InProgress,
            Assignee = new User { Key = "assignee-key" }
        });

        await _client.Tasks.UpdateAsync(task.Id, new TaskUpdateRequest
        {
            Summary = "Implement C# Agent with Jira",
            Description = "This task is to integrate C# Agent with Jira for tracking activities.",
            Status = TaskStatus.Done,
            Assignee = null
        });

        var completedTask = await _client.Tasks.GetAsync(task.Id);

        Assert.NotNull(completedTask);
        Assert.Equal("NEWPRJ-1", completedTask.Key);
        Assert.Equal(TaskStatus.Done, completedTask.Status);
    }
}