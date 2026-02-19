using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

class Program
{
    static async Task Main(string[] args)
    {
        // Initialize Jira client with your credentials
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Create a new issue
        var issue = new Issue()
        {
            Summary = "New Test Case",
            Description = "This is a test case for the C# Agent integration.",
            ProjectKey = "YOUR-PROJECT-KEY",
            TypeId = 1, // Bug type ID in Jira
            PriorityId = 3, // High priority ID in Jira
            AssigneeId = 123456789, // Assignee ID in Jira
        };

        // Create the issue in Jira
        var createdIssue = await jiraClient.Issue.Create(issue);

        Console.WriteLine($"Issue created: {createdIssue.Key}");

        // Close the issue
        var closeIssueRequest = new IssueUpdate()
        {
            StatusId = 10, // Closed status ID in Jira
        };

        await jiraClient.Issue.Update(createdIssue.Key, closeIssueRequest);

        Console.WriteLine("Issue closed.");
    }
}

class ProgramTests
{
    [Fact]
    public async Task CreateIssueTest()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
        var issue = new Issue()
        {
            Summary = "New Test Case",
            Description = "This is a test case for the C# Agent integration.",
            ProjectKey = "YOUR-PROJECT-KEY",
            TypeId = 1, // Bug type ID in Jira
            PriorityId = 3, // High priority ID in Jira
            AssigneeId = 123456789, // Assignee ID in Jira
        };

        var createdIssue = await jiraClient.Issue.Create(issue);

        Assert.NotNull(createdIssue);
    }

    [Fact]
    public async Task UpdateIssueTest()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
        var issue = new Issue()
        {
            Summary = "New Test Case",
            Description = "This is a test case for the C# Agent integration.",
            ProjectKey = "YOUR-PROJECT-KEY",
            TypeId = 1, // Bug type ID in Jira
            PriorityId = 3, // High priority ID in Jira
            AssigneeId = 123456789, // Assignee ID in Jira
        };

        var createdIssue = await jiraClient.Issue.Create(issue);

        var closeIssueRequest = new IssueUpdate()
        {
            StatusId = 10, // Closed status ID in Jira
        };

        await jiraClient.Issue.Update(createdIssue.Key, closeIssueRequest);

        Assert.NotNull(createdIssue);
    }
}