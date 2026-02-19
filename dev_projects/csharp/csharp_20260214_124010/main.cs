using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        try
        {
            await jiraClient.LoginAsync();

            Console.WriteLine("Logged in successfully!");

            // Example: Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully!");

            // Example: Update an existing issue
            var update = new IssueUpdate
            {
                Description = "This is an updated test issue."
            };

            await jiraClient.UpdateIssueAsync(issue.Key, update);

            Console.WriteLine("Issue updated successfully!");

            // Example: Delete an issue
            await jiraClient.DeleteIssueAsync(issue.Key);

            Console.WriteLine("Issue deleted successfully!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }
    }
}