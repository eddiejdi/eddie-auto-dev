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
            var issues = await jiraClient.GetIssuesAsync();

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Key}, Summary: {issue.Fields.Summary}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}