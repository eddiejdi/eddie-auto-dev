using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharpClient;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Create a new project
        var project = await client.Projects.CreateAsync(new ProjectCreateRequest
        {
            Key = "PRJ1",
            Name = "My Project"
        });

        Console.WriteLine($"Project created: {project.Key}");

        // Create a new issue
        var issue = await client.Issues.CreateAsync(new IssueCreateRequest
        {
            ProjectKey = project.Key,
            Summary = "Test Issue",
            Description = "This is a test issue for the C# Agent integration."
        });

        Console.WriteLine($"Issue created: {issue.Id}");

        // Log a message to Jira
        await client.Logs.CreateAsync(new LogCreateRequest
        {
            ProjectKey = project.Key,
            IssueId = issue.Id,
            Message = "This is a test log entry from the C# Agent integration."
        });

        Console.WriteLine("Log created successfully.");
    }
}