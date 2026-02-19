using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateTaskAsync_WithValidData_ShouldReturnTask()
    {
        // Arrange
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Act
        var task = await jira.CreateTaskAsync(new TaskCreateRequest
        {
            Summary = "Implementar C# Agent com Jira",
            Description = "Integrar C# Agent com Jira - tracking de atividades"
        });

        // Assert
        Assert.NotNull(task);
    }

    [Fact]
    public async Task CreateTaskAsync_WithInvalidSummary_ShouldThrowException()
    {
        // Arrange
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Act
        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateTaskAsync(new TaskCreateRequest
        {
            Summary = null,
            Description = "Integrar C# Agent com Jira - tracking de atividades"
        }));
    }

    [Fact]
    public async Task CreateTaskAsync_WithInvalidDescription_ShouldThrowException()
    {
        // Arrange
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Act
        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateTaskAsync(new TaskCreateRequest
        {
            Summary = "Implementar C# Agent com Jira",
            Description = null
        }));
    }
}