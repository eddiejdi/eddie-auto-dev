using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Initialize Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a new issue in Jira
            var issue = new Issue
            {
                Summary = "New task from C# Agent",
                Description = "This is a test task created by the C# Agent for tracking purposes.",
                Priority = "High",
                Status = "To Do"
            };

            // Add the issue to Jira
            await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully in Jira.");
        }
    }

    class Issue
    {
        public string Summary { get; set; }
        public string Description { get; set; }
        public string Priority { get; set; }
        public string Status { get; set; }
    }
}