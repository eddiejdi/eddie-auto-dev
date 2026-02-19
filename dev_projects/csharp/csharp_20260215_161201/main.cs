using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Example: Create a new issue
        var issue = new Issue
        {
            Summary = "New Feature Request",
            Description = "Implement a new feature in the application.",
            ProjectKey = "YOUR-PROJECT-KEY"
        };

        await jiraClient.CreateIssueAsync(issue);

        Console.WriteLine("Issue created successfully.");
    }
}