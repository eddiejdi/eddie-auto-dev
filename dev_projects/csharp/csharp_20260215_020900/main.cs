using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        try
        {
            // Crie uma instância do cliente Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Criar um novo ticket no Jira
            var issue = await client.CreateIssueAsync(
                "My New Issue",
                "This is a test issue.",
                "bug"
            );

            Console.WriteLine($"Ticket created: {issue.Key}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}