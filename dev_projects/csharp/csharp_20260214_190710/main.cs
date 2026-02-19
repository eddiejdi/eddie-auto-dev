using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Example: Create a new issue
        Issue issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Test Issue",
            Description = "This is a test issue created using JiraSharp.",
            Priority = new Priority { Name = "High" },
            Assignee = new User { Key = "assignee-key" }
        };

        var createdIssue = await jiraClient.Issue.CreateAsync(issue);

        Console.WriteLine($"Created Issue: {createdIssue.Key}");

        // Example: Update an issue
        issue.Description = "Updated description for the test issue.";
        updatedIssue = await jiraClient.Issue.UpdateAsync(createdIssue.Key, issue);

        Console.WriteLine($"Updated Issue: {updatedIssue.Key}");

        // Example: Delete an issue
        await jiraClient.Issue.DeleteAsync(createdIssue.Key);

        Console.WriteLine("Deleted Issue.");
    }
}