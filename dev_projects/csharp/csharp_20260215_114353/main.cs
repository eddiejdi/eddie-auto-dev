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
            // Initialize the Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "New issue created by C# Agent",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Create the issue in Jira
            await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully!");
        }
    }

    class Issue
    {
        public string Summary { get; set; }
        public string Description { get; set; }
        public string ProjectKey { get; set; }
    }
}