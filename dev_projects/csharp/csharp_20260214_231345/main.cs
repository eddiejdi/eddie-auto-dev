using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Função para criar um novo ticket no Jira
        await CreateTicket(client, "New Feature Request", "Implement a new feature for the application.");

        // Função para buscar tickets por título
        var tickets = await client.SearchTickets("New Feature Request");
        foreach (var ticket in tickets)
        {
            Console.WriteLine($"Ticket ID: {ticket.Id}, Summary: {ticket.Summary}");
        }
    }

    static async Task CreateTicket(JiraClient client, string summary, string description)
    {
        try
        {
            var newTicket = new NewIssueRequest()
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                IssueType = "Bug",
                Summary = summary,
                Description = description
            };

            await client.CreateIssue(newTicket);
            Console.WriteLine("Ticket created successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating ticket: {ex.Message}");
        }
    }
}