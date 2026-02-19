using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssueAsync_WithValidInputs_ShouldReturnCreatedIssue()
    {
        // Arrange
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
        var issueData = new Dictionary<string, object>
        {
            { "fields.summary", "New Feature" },
            { "fields.description", "This is a new feature request." },
            { "fields.project.key", "SCRUM-14" },
            { "fields.issuetype.name", "bug" }
        };

        // Act
        var issue = await jiraClient.CreateIssueAsync(issueData);

        // Assert
        Assert.NotNull(issue);
        Assert.NotEmpty(issue.Key);
    }

    [Fact]
    public async Task CreateIssueAsync_WithInvalidInputs_ShouldThrowException()
    {
        // Arrange
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
        var issueData = new Dictionary<string, object>
        {
            { "fields.summary", "" },
            { "fields.description", null },
            { "fields.project.key", "SCRUM-14" },
            { "fields.issuetype.name", "bug" }
        };

        // Act
        await jiraClient.CreateIssueAsync(issueData);

        // Assert
        var exception = await Task.Run(() => jiraClient.CreateIssueAsync(issueData));
        Assert.IsType<ArgumentException>(exception);
    }
}