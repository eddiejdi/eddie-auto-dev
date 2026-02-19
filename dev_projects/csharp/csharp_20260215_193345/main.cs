using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharpClient;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Create a new issue
                var issue = await client.CreateIssueAsync(
                    "New Issue",
                    "This is a new issue created by the C# Agent.",
                    "bug"
                );

                Console.WriteLine($"Created issue: {issue.Key}");

                // Update an existing issue
                var updatedIssue = await client.UpdateIssueAsync(issue.Key, "Updated description", "feature");

                Console.WriteLine($"Updated issue: {updatedIssue.Key}");

                // Delete an issue
                await client.DeleteIssueAsync(issue.Key);

                Console.WriteLine("Deleted issue.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
        }
    }
}