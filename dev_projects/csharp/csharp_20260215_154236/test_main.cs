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
    public async Task TestCreateProject()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var project = await client.Projects.Create(new Project { Key = "NEWPROJECT", Name = "New Project", Description = "This is a new project for tracking activities." });
        Assert.NotNull(project);
    }

    [Fact]
    public async Task TestCreateIssue()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var issue = await client.Issues.Create(new Issue { Key = "NEWISSUE", Summary = "New Issue", Description = "This is a new issue for tracking activities.", ProjectId = 1, AssigneeId = 1 });
        Assert.NotNull(issue);
    }

    [Fact]
    public async Task TestCreateTask()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var task = await client.Tasks.Create(new Task { Key = "NEWTASK", Summary = "New Task", Description = "This is a new task for tracking activities.", IssueId = 1, AssigneeId = 1 });
        Assert.NotNull(task);
    }

    [Fact]
    public async Task TestCreateActivity()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        var activity = await client.Activities.Create(new Activity { Key = "NEWACTIVITY", Summary = "New Activity", Description = "This is a new activity for tracking activities.", TaskId = 1, StatusId = 1 });
        Assert.NotNull(activity);
    }
}