using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue
        var issue = new Issue()
        {
            Summary = "Test Issue",
            Description = "This is a test issue created by the C# Agent.",
            Priority = "High",
            Status = "Open"
        };

        await jira.CreateIssueAsync(issue);

        Console.WriteLine("Issue created successfully.");
    }
}