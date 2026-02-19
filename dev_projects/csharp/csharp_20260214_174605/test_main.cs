using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _jiraClient;

    public ProgramTests()
    {
        _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
    }

    [Fact]
    public async Task CreateIssue_Successfully()
    {
        var issue = new Issue
        {
            Summary = "New C# Agent Integration",
            Description = "This is an integration of the C# Agent with Jira for tracking activities.",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        await _jiraClient.CreateIssue(issue);

        // Additional assertions can be added here if needed
    }

    [Fact]
    public async Task CreateIssue_ThrowsException_WhenSummaryIsNull()
    {
        var issue = new Issue
        {
            Description = "This is an integration of the C# Agent with Jira for tracking activities.",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.CreateIssue(issue));
    }

    [Fact]
    public async Task GetIssues_Successfully()
    {
        var issues = await _jiraClient.GetIssues("YOUR_PROJECT_KEY");

        // Additional assertions can be added here if needed
    }

    [Fact]
    public async Task GetIssues_ThrowsException_WhenProjectKeyIsNull()
    {
        var issues = await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.GetIssues(null));
    }
}