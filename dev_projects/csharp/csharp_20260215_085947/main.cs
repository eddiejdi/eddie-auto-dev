using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            await jiraClient.CreateIssueAsync("New Issue", "This is a new issue created by the C# Agent.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating issue: {ex.Message}");
        }

        Console.WriteLine("C# Agent successfully integrated with Jira.");
    }
}