using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New C# Agent Integration",
            Description = "Integrate C# Agent with Jira for tracking activities.",
            Priority = Priority.High,
            Assignee = new User { Name = "your-username" }
        };

        var createdIssue = await jiraClient.CreateIssue(issue);

        Console.WriteLine($"Created issue: {createdIssue.Key}");

        // Get all issues
        var issues = await jiraClient.GetIssues();

        foreach (var issue in issues)
        {
            Console.WriteLine($"Issue: {issue.Key}, Summary: {issue.Summary}");
        }

        // Update an existing issue
        var updateIssue = new Issue
        {
            Id = createdIssue.Id,
            Description = "Updated description for the C# Agent integration."
        };

        await jiraClient.UpdateIssue(updateIssue);

        Console.WriteLine($"Updated issue: {updateIssue.Key}");

        // Delete an issue
        await jiraClient.DeleteIssue(createdIssue.Id);

        Console.WriteLine("Deleted issue.");
    }
}