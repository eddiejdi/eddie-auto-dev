using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssueAsync_WithValidData_ShouldSucceed()
    {
        // Arrange
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Example Task",
            Description = "This is an example task.",
            Priority = "High",
            Status = "To Do"
        };

        // Act
        await client.CreateIssueAsync(issue);

        // Assert
        Assert.True(true); // Replace with actual assertion logic
    }

    [Fact]
    public async Task CreateIssueAsync_WithInvalidData_ShouldThrowException()
    {
        // Arrange
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "",
            Description = null,
            Priority = "High",
            Status = "To Do"
        };

        // Act and Assert
        await Assert.ThrowsAsync<Exception>(async () => await client.CreateIssueAsync(issue));
    }
}