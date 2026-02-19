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
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Create a new issue
        var issue = new Issue
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "Test issue",
            Description = "This is a test issue created by C# Agent.",
            Priority = Priority.High,
            Status = Status.Open
        };

        await jiraClient.CreateIssue(issue);

        Console.WriteLine("Issue created successfully.");
    }
}