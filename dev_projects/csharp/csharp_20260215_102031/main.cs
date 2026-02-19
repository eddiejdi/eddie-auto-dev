using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issues = await jiraClient.GetIssuesAsync(new GetIssuesOptions { Fields = new List<string> { "summary", "status" } });

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key}, Summary: {issue.Fields.Summary}, Status: {issue.Fields.Status.Name}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}