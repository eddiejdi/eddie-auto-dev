using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        try
        {
            var issues = await client.GetIssuesAsync();
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