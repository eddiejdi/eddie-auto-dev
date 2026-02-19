using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _client;

    public ProgramTests()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        _client = client;
    }

    [Fact]
    public async Task CreateTaskAsync_Success()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var summary = "New C# Agent Integration";
        var description = "This is a new task to integrate the C# Agent with Jira.";

        var issue = await _client.CreateIssueAsync(
            projectKey,
            summary,
            description
        );

        Assert.NotNull(issue);
    }

    [Fact]
    public async Task CreateTaskAsync_Failure_InvalidSummary()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var summary = "";
        var description = "This is a new task to integrate the C# Agent with Jira.";

        await _client.CreateIssueAsync(
            projectKey,
            summary,
            description
        );

        Assert.Null(await _client.GetIssuesAsync(projectKey));
    }

    [Fact]
    public async Task ListTasksAsync_Success()
    {
        var projectKey = "YOUR_PROJECT_KEY";

        var issues = await _client.GetIssuesAsync(projectKey);

        Assert.NotEmpty(issues);
    }

    [Fact]
    public async Task UpdateTaskAsync_Success()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var issueKey = "YOUR_TASK_KEY";
        var summary = "Updated C# Agent Integration";
        var description = "This is an updated task to integrate the C# Agent with Jira.";

        await _client.UpdateIssueAsync(
            projectKey,
            issueKey,
            summary,
            description
        );

        var updatedIssue = await _client.GetIssuesAsync(projectKey).FirstOrDefault(i => i.Key == issueKey);

        Assert.NotNull(updatedIssue);
    }

    [Fact]
    public async Task UpdateTaskAsync_Failure_InvalidSummary()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var issueKey = "YOUR_TASK_KEY";
        var summary = "";
        var description = "This is an updated task to integrate the C# Agent with Jira.";

        await _client.UpdateIssueAsync(
            projectKey,
            issueKey,
            summary,
            description
        );

        var updatedIssue = await _client.GetIssuesAsync(projectKey).FirstOrDefault(i => i.Key == issueKey);

        Assert.Null(updatedIssue);
    }

    [Fact]
    public async Task DeleteTaskAsync_Success()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var issueKey = "YOUR_TASK_KEY";

        await _client.DeleteIssueAsync(projectKey, issueKey);

        var deletedIssue = await _client.GetIssuesAsync(projectKey).FirstOrDefault(i => i.Key == issueKey);

        Assert.Null(deletedIssue);
    }

    [Fact]
    public async Task DeleteTaskAsync_Failure_InvalidIssueKey()
    {
        var projectKey = "YOUR_PROJECT_KEY";
        var issueKey = "";

        await _client.DeleteIssueAsync(projectKey, issueKey);

        var deletedIssue = await _client.GetIssuesAsync(projectKey).FirstOrDefault(i => i.Key == issueKey);

        Assert.Null(deletedIssue);
    }
}