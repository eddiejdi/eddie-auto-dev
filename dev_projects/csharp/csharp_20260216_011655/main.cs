using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do Jira API
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para criar um novo issue no Jira
        async Task CreateIssueAsync(string summary, string description)
        {
            var issue = new Issue
            {
                Summary = summary,
                Description = description,
                ProjectKey = "YOUR_PROJECT_KEY",
                PriorityId = 1, // Poderia ser ajustado conforme necessário
                AssigneeId = 2, // Poderia ser ajustado conforme necessário
            };

            var createdIssue = await jiraClient.Issue.CreateAsync(issue);
            Console.WriteLine($"Created issue: {createdIssue.Key}");
        }

        // Função para listar todas as issues do projeto
        async Task ListIssuesAsync()
        {
            var issues = await jiraClient.Issue.GetAllAsync();
            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key}, Summary: {issue.Summary}");
            }
        }

        // Exemplo de uso das funções
        await CreateIssueAsync("Teste C# Agent", "Este é um teste para o C# Agent no Jira.");
        await ListIssuesAsync();
    }
}