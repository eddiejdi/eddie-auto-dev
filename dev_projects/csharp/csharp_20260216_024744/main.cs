using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

namespace Scrum14Agent
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue()
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "New Scrum 14 Task",
                Description = "This is a new task for the Scrum 14 project.",
                Priority = "High"
            };

            await jiraClient.CreateIssueAsync(issue);

            // Get all issues in the project
            var issues = await jiraClient.GetIssuesAsync("YOUR_PROJECT_KEY");

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Id}, Summary: {issue.Summary}");
            }

            // Update an existing issue
            var update = new IssueUpdate()
            {
                Description = "This is an updated description for the Scrum 14 task."
            };

            await jiraClient.UpdateIssueAsync(issue.Id, update);

            // Delete an existing issue
            await jiraClient.DeleteIssueAsync(issue.Id);
        }
    }
}