using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a new issue
        var issue = new Issue
        {
            Summary = "New C# Agent Integration",
            Description = "This is an integration of the C# Agent with Jira for tracking activities.",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        await jiraClient.CreateIssue(issue);

        // Get all issues in a project
        var issues = await jiraClient.GetIssues("YOUR_PROJECT_KEY");

        foreach (var issue in issues)
        {
            Console.WriteLine($"Issue ID: {issue.Id}");
            Console.WriteLine($"Summary: {issue.Summary}");
            Console.WriteLine($"Description: {issue.Description}");
            Console.WriteLine($"Status: {issue.Status.Name}");
            Console.WriteLine();
        }
    }
}