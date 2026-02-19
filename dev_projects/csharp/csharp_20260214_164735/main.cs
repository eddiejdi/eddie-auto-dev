using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do JiraSharp
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar um novo ticket
            var issue = new Issue
            {
                Summary = "Teste C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Type = "Bug"
            };

            // Criar a tarefa no Jira
            var createdIssue = await jira.CreateIssueAsync(issue);
            Console.WriteLine($"Ticket criado: {createdIssue.Key}");

            // Atualizar o ticket
            issue.Status = "In Progress";
            await jira.UpdateIssueAsync(createdIssue.Key, issue);

            // Fechar o ticket
            issue.Status = "Closed";
            await jira.UpdateIssueAsync(createdIssue.Key, issue);
        }
    }
}