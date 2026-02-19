using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task TestCreateIssue()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        Issue issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Test Issue",
            Description = "This is a test issue created using JiraSharp.",
            Priority = new Priority { Name = "High" },
            Assignee = new User { Key = "assignee-key" }
        };

        var createdIssue = await jiraClient.Issue.CreateAsync(issue);

        Assert.NotNull(createdIssue);
        Assert.NotEmpty(createdIssue.Key);
    }

    [Fact]
    public async Task TestUpdateIssue()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        Issue issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Test Issue",
            Description = "This is a test issue created using JiraSharp.",
            Priority = new Priority { Name = "High" },
            Assignee = new User { Key = "assignee-key" }
        };

        var createdIssue = await jiraClient.Issue.CreateAsync(issue);

        if (createdIssue != null)
        {
            issue.Description = "Updated description for the test issue.";
            updatedIssue = await jiraClient.Issue.UpdateAsync(createdIssue.Key, issue);

            Assert.NotNull(updatedIssue);
            Assert.NotEmpty(updatedIssue.Key);
        }
    }

    [Fact]
    public async Task TestDeleteIssue()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        Issue issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Test Issue",
            Description = "This is a test issue created using JiraSharp.",
            Priority = new Priority { Name = "High" },
            Assignee = new User { Key = "assignee-key" }
        };

        var createdIssue = await jiraClient.Issue.CreateAsync(issue);

        if (createdIssue != null)
        {
            await jiraClient.Issue.DeleteAsync(createdIssue.Key);

            Issue deletedIssue = await jiraClient.Issue.GetAsync(createdIssue.Key);
            Assert.Null(deletedIssue);
        }
    }
}