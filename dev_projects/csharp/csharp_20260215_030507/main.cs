using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

namespace CSharpAgent
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            var project = await client.Projects.GetProjectAsync("PROJECT_KEY");
            var issues = await client.Issues.GetAllIssuesAsync(project.Id);

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Key}, Summary: {issue.Summary}");
            }
        }
    }
}