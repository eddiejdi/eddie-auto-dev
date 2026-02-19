using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        try
        {
            // Configurar o cliente do Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Criar um novo issue
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "Example Task",
                Description = "This is an example task.",
                Priority = "High",
                Status = "To Do"
            };

            // Adicionar o issue ao Jira
            await client.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }
    }
}