using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            await client.CreateIssueAsync("Bug", "This is a test bug");
            Console.WriteLine("Issue created successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating issue: {ex.Message}");
        }
    }
}