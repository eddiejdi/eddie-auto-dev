using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.JiraClient;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

    [Fact]
    public async Task CreateIssueAsync_Success()
    {
        var issue = new Issue
        {
            Summary = "New Test Issue",
            Description = "This is a test issue created using C# Agent with Jira.",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        var createdIssue = await _jiraClient.CreateIssueAsync(issue);

        Assert.NotNull(createdIssue);
        Assert.NotEmpty(createdIssue.Key);
    }

    [Fact]
    public async Task CreateIssueAsync_Failure()
    {
        var issue = new Issue
        {
            Summary = "New Test Issue",
            Description = "",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        await _jiraClient.CreateIssueAsync(issue);

        Assert.Null(await _jiraClient.GetIssueAsync(issue.Id));
    }

    [Fact]
    public async Task UpdateIssueAsync_Success()
    {
        var issue = new Issue
        {
            Id = 1,
            Summary = "Updated Test Issue",
            Description = "This is an updated test issue created using C# Agent with Jira."
        };

        await _jiraClient.UpdateIssueAsync(issue);

        var updatedIssue = await _jiraClient.GetIssueAsync(issue.Id);

        Assert.NotNull(updatedIssue);
        Assert.NotEmpty(updatedIssue.Key);
    }

    [Fact]
    public async Task UpdateIssueAsync_Failure()
    {
        var issue = new Issue
        {
            Id = 1,
            Summary = "",
            Description = "This is an updated test issue created using C# Agent with Jira."
        };

        await _jiraClient.UpdateIssueAsync(issue);

        Assert.Null(await _jiraClient.GetIssueAsync(issue.Id));
    }

    [Fact]
    public async Task DeleteIssueAsync_Success()
    {
        var issue = new Issue
        {
            Id = 1,
            Summary = "Deleted Test Issue",
            Description = "This is a deleted test issue created using C# Agent with Jira."
        };

        await _jiraClient.DeleteIssueAsync(issue.Id);

        Assert.Null(await _jiraClient.GetIssueAsync(issue.Id));
    }

    [Fact]
    public async Task DeleteIssueAsync_Failure()
    {
        var issue = new Issue
        {
            Id = 1,
            Summary = "",
            Description = "This is a deleted test issue created using C# Agent with Jira."
        };

        await _jiraClient.DeleteIssueAsync(issue.Id);

        Assert.Null(await _jiraClient.GetIssueAsync(issue.Id));
    }
}