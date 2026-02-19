using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issues = await jira.GetIssuesAsync();

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key} - Status: {issue.Fields.Status.Name}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error: " + ex.Message);
        }
    }
}