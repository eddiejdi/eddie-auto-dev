using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue
        var issue = new Issue
        {
            Summary = "Test Issue",
            Description = "This is a test issue created by the C# Agent for Jira integration.",
            ProjectKey = "YOUR_PROJECT_KEY",
            Priority = new Priority { Id = 1 },
            Assignee = new User { Name = "your-username" }
        };

        var createdIssue = await jiraClient.CreateIssue(issue);

        Console.WriteLine($"Created issue: {createdIssue.Key}");

        // Update the issue
        issue.Status = new Status { Id = 2 }; // In Progress

        await jiraClient.UpdateIssue(createdIssue.Key, issue);

        Console.WriteLine($"Updated issue status to In Progress.");

        // Close the issue
        issue.Status = new Status { Id = 3 }; // Closed

        await jiraClient.CloseIssue(createdIssue.Key, issue);

        Console.WriteLine($"Closed issue.");
    }
}