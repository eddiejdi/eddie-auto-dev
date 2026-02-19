using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssueAsync_ShouldCreateNewIssue()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue
        var issue = new Issue
        {
            Summary = "New feature request",
            Description = "Implement a new feature in the application.",
            Priority = "High"
        };

        var createdIssue = await client.CreateIssueAsync(issue);

        Assert.NotNull(createdIssue);
    }

    [Fact]
    public async Task CreateIssueAsync_ShouldThrowExceptionForInvalidSummary()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue with an invalid summary
        var issue = new Issue
        {
            Summary = null,
            Description = "Implement a new feature in the application.",
            Priority = "High"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => client.CreateIssueAsync(issue));
    }

    [Fact]
    public async Task UpdateIssueAsync_ShouldUpdateExistingIssue()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue
        var issue = new Issue
        {
            Summary = "New feature request",
            Description = "Implement a new feature in the application.",
            Priority = "High"
        };

        var createdIssue = await client.CreateIssueAsync(issue);

        // Update an existing issue
        var update = new IssueUpdate
        {
            Summary = "Updated feature request",
            Description = "Implement a new feature in the application."
        };

        var updatedIssue = await client.UpdateIssueAsync(createdIssue.Key, update);

        Assert.NotNull(updatedIssue);
    }

    [Fact]
    public async Task UpdateIssueAsync_ShouldThrowExceptionForInvalidSummary()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue with an invalid summary
        var issue = new Issue
        {
            Summary = null,
            Description = "Implement a new feature in the application.",
            Priority = "High"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => client.UpdateIssueAsync(issue.Key, update));
    }

    [Fact]
    public async Task DeleteIssueAsync_ShouldDeleteExistingIssue()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue
        var issue = new Issue
        {
            Summary = "New feature request",
            Description = "Implement a new feature in the application.",
            Priority = "High"
        };

        var createdIssue = await client.CreateIssueAsync(issue);

        // Delete an existing issue
        await client.DeleteIssueAsync(createdIssue.Key);
    }
}