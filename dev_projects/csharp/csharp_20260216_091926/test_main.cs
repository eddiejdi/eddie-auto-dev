using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssueTest()
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with valid data
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New C# Agent Integration",
            Description = "Integrate C# Agent with Jira for tracking activities.",
            Priority = Priority.High,
            Assignee = new User { Name = "your-username" }
        };

        var createdIssue = await jiraClient.CreateIssue(issue);

        // Assert that the issue was created successfully
        Assert.NotNull(createdIssue);
        Assert.NotEmpty(createdIssue.Key);
    }

    [Fact]
    public async Task CreateIssueTestWithInvalidData()
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with invalid data
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "",
            Description = "Integrate C# Agent with Jira for tracking activities.",
            Priority = Priority.High,
            Assignee = new User { Name = "your-username" }
        };

        try
        {
            await jiraClient.CreateIssue(issue);
        }
        catch (Exception ex)
        {
            // Assert that the exception is thrown when invalid data is provided
            Assert.Contains("Invalid project key", ex.Message);
        }
    }

    [Fact]
    public async Task GetIssuesTest()
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Get all issues
        var issues = await jiraClient.GetIssues();

        // Assert that the list of issues is not empty
        Assert.NotEmpty(issues);
    }

    [Fact]
    public async Task UpdateIssueTest()
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with valid data
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New C# Agent Integration",
            Description = "Integrate C# Agent with Jira for tracking activities.",
            Priority = Priority.High,
            Assignee = new User { Name = "your-username" }
        };

        var createdIssue = await jiraClient.CreateIssue(issue);

        // Update the issue with valid data
        var updateIssue = new Issue
        {
            Id = createdIssue.Id,
            Description = "Updated description for the C# Agent integration."
        };

        await jiraClient.UpdateIssue(updateIssue);

        // Assert that the issue was updated successfully
        var updatedIssue = await jiraClient.GetIssue(createdIssue.Id);
        Assert.NotEmpty(updatedIssue.Description);
    }

    [Fact]
    public async Task DeleteIssueTest()
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with valid data
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New C# Agent Integration",
            Description = "Integrate C# Agent with Jira for tracking activities.",
            Priority = Priority.High,
            Assignee = new User { Name = "your-username" }
        };

        var createdIssue = await jiraClient.CreateIssue(issue);

        // Delete the issue
        await jiraClient.DeleteIssue(createdIssue.Id);

        // Assert that the issue was deleted successfully
        try
        {
            await jiraClient.GetIssue(createdIssue.Id);
        }
        catch (Exception ex)
        {
            // Assert that the exception is thrown when trying to retrieve a non-existent issue
            Assert.Contains("No issue found with ID", ex.Message);
        }
    }
}