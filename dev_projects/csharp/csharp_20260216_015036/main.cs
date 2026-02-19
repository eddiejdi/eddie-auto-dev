using System;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Initialize Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "New Task",
                Description = "This is a new task created by the C# Agent.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Create the issue in Jira
            await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully.");
        }
    }

    class Issue
    {
        public string Summary { get; set; }
        public string Description { get; set; }
        public string ProjectKey { get; set; }
    }
}