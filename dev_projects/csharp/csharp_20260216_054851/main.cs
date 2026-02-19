using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
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

        Console.WriteLine($"Created issue: {createdIssue.Key}");

        // Update an existing issue
        var update = new IssueUpdate
        {
            Summary = "Updated feature request",
            Description = "Implement a new feature in the application."
        };

        var updatedIssue = await client.UpdateIssueAsync(createdIssue.Key, update);

        Console.WriteLine($"Updated issue: {updatedIssue.Key}");

        // Delete an existing issue
        await client.DeleteIssueAsync(createdIssue.Key);
    }
}