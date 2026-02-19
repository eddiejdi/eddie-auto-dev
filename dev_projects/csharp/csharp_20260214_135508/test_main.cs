using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssueAsync_Successful()
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with valid data
        var issue = new Issue()
        {
            Summary = "Test Issue",
            Description = "This is a test issue created by the C# Agent.",
            Priority = "High",
            Status = "Open"
        };

        await jira.CreateIssueAsync(issue);

        // Assert that the issue was created successfully
        Assert.True(jira.Issues.Any(i => i.Key == issue.Key));
    }

    [Fact]
    public async Task CreateIssueAsync_InvalidSummary()
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with an invalid summary
        var issue = new Issue()
        {
            Summary = null,
            Description = "This is a test issue created by the C# Agent.",
            Priority = "High",
            Status = "Open"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateIssueAsync(issue));
    }

    [Fact]
    public async Task CreateIssueAsync_InvalidDescription()
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with an invalid description
        var issue = new Issue()
        {
            Summary = "Test Issue",
            Description = null,
            Priority = "High",
            Status = "Open"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateIssueAsync(issue));
    }

    [Fact]
    public async Task CreateIssueAsync_InvalidPriority()
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with an invalid priority
        var issue = new Issue()
        {
            Summary = "Test Issue",
            Description = "This is a test issue created by the C# Agent.",
            Priority = null,
            Status = "Open"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateIssueAsync(issue));
    }

    [Fact]
    public async Task CreateIssueAsync_InvalidStatus()
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue with an invalid status
        var issue = new Issue()
        {
            Summary = "Test Issue",
            Description = "This is a test issue created by the C# Agent.",
            Priority = "High",
            Status = null
        };

        await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateIssueAsync(issue));
    }
}