using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue
        var issue = new Issue
        {
            Summary = "Teste de Integração",
            Description = "Este é um teste para integrar o C# Agent com Jira.",
            Type = new IssueType { Name = "Bug" }
        };

        // Cria a issue no Jira
        await client.Issue.CreateAsync(issue);

        Console.WriteLine("Issue criado com sucesso!");
    }
}