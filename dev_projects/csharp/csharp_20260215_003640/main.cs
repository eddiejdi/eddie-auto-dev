using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Função para criar um novo ticket no Jira
        async Task CreateTicketAsync(string summary, string description)
        {
            var issue = new Issue
            {
                Summary = summary,
                Description = description,
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 }, // Prioridade alta
                Assignee = new Assignee { Username = "your-assignee-username" } // Colaborador
            };

            var createdIssue = await client.Issue.CreateAsync(issue);
            Console.WriteLine($"Ticket criado com ID: {createdIssue.Id}");
        }

        // Função para buscar um ticket no Jira
        async Task GetTicketAsync(string issueId)
        {
            var issue = await client.Issue.GetAsync(issueId);
            Console.WriteLine($"Detalhes do ticket:");
            Console.WriteLine($"ID: {issue.Id}");
            Console.WriteLine($"Summary: {issue.Summary}");
            Console.WriteLine($"Description: {issue.Description}");
        }

        // Exemplo de uso das funções
        await CreateTicketAsync("Teste C# Agent", "Integração com Jira - tracking de atividades");
        await GetTicketAsync("YOUR_TICKET_ID"); // Substitua pelo ID do ticket criado no exemplo anterior
    }
}