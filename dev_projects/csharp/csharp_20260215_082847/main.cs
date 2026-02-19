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
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue
        var issue = new Issue()
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New Task",
            Description = "This is a new task created by the C# Agent.",
            Priority = new Priority() { Name = "High" },
            Assignee = new User() { Key = "YOUR_USER_KEY" }
        };

        // Adiciona o issue ao Jira
        var addedIssue = await jiraClient.CreateIssueAsync(issue);

        Console.WriteLine($"Issue created: {addedIssue.Key}");
    }
}