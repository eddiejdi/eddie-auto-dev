using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Cria um novo ticket no Jira
        var issue = await jira.CreateIssueAsync(
            projectKey: "YOUR-PROJECT",
            summary: "Teste de Integração",
            description: "Este é um teste para integrar o C# Agent com Jira.",
            priority: new Priority { Name = "High" },
            assignee: new Assignee { Username = "assignee-username" }
        );

        Console.WriteLine($"Ticket criado com ID: {issue.Id}");
    }
}