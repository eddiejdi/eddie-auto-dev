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
        // Configuração do cliente Jira
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue
        var issue = new Issue
        {
            Key = "TEST-1",
            Summary = "Teste de integração C# Agent com Jira",
            Description = "Este é um teste para integrar o C# Agent com Jira.",
            Priority = new Priority { Name = "High" },
            Status = new Status { Name = "To Do" }
        };

        // Adiciona a issue ao projeto
        var project = await jiraClient.GetProjectAsync("your-project-key");
        var issueResult = await jiraClient.CreateIssueAsync(project.Key, issue);

        Console.WriteLine($"Issue criado com ID: {issueResult.Id}");
    }
}