using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Create a new issue
            var issue = await jiraClient.CreateIssueAsync(
                "New Issue",
                "This is a new issue created by the CSharp Agent.",
                "bug"
            );

            Console.WriteLine($"Created issue with ID: {issue.Id}");

            // Example: Update an existing issue
            var updatedIssue = await jiraClient.UpdateIssueAsync(issue.Id, "Updated issue title", "This is an updated issue description.");

            Console.WriteLine($"Updated issue with ID: {updatedIssue.Id}");

            // Example: Delete an issue
            await jiraClient.DeleteIssueAsync(issue.Id);

            Console.WriteLine("Deleted issue successfully.");
        }
    }
}