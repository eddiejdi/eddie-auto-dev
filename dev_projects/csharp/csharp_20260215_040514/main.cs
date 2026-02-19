using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            try
            {
                // Initialize Jira client
                var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

                // Create a new issue
                var issue = new Issue
                {
                    Summary = "New task",
                    Description = "This is a new task created by CSharpAgentJiraIntegration",
                    ProjectKey = "YOUR_PROJECT_KEY"
                };

                // Create the issue in Jira
                var createdIssue = await jiraClient.CreateIssueAsync(issue);

                Console.WriteLine($"Issue created successfully: {createdIssue.Key}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
            }
        }
    }

    class Issue
    {
        public string Summary { get; set; }
        public string Description { get; set; }
        public string ProjectKey { get; set; }
    }
}