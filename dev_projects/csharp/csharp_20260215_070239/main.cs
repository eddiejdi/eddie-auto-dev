using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.JiraClient;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        try
        {
            // Create a new issue
            var issue = new Issue
            {
                Summary = "New Test Issue",
                Description = "This is a test issue created using C# Agent with Jira.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            var createdIssue = await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine($"Created issue: {createdIssue.Key}");

            // Update the issue
            var updatedIssue = new Issue
            {
                Id = createdIssue.Id,
                Summary = "Updated Test Issue",
                Description = "This is an updated test issue created using C# Agent with Jira."
            };

            await jiraClient.UpdateIssueAsync(updatedIssue);

            Console.WriteLine($"Updated issue: {updatedIssue.Key}");

            // Delete the issue
            await jiraClient.DeleteIssueAsync(createdIssue.Id);

            Console.WriteLine("Deleted issue.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}